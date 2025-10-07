from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework import status
from django.contrib.auth.models import User
import grpc
import exam_pb2  # Ensure this matches the generated file location (e.g., from exams or exams.protos)
from .models import Exam, ExamAssignment
from datetime import date
import unittest
from .grpc_server import ExamService
from .exam_client import ExamGRPCClient
from .grpc_client import UserGRPCClient

class ExamViewsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        Exam.objects.all().delete()
        ExamAssignment.objects.all().delete()
        self.user_teacher = User.objects.create_user(username='teacher', password='testpass')
        self.user_student = User.objects.create_user(username='student', password='testpass')
        self.user_teacher.teacher = type('obj', (object,), {'id': 1})()
        self.user_student.student = type('obj', (object,), {'id': 1})()
        self.teacher_data = MagicMock(teacher_id=1, first_name='Teacher', user_id=self.user_teacher.id)
        self.student_data = MagicMock(student_id=1, first_name='Student', user_id=self.user_student.id)
        self.exam_data = {
            'title': 'Test Exam',
            'subject': 'Math',
            'date': '2025-10-10',
            'duration': 60,
            'teacher_id': 1
        }

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    @patch('exams.views.ExamGRPCClient.create_exam')
    def test_create_exam_success(self, mock_create_exam, mock_get_teacher):
        mock_get_teacher.return_value = self.teacher_data
        mock_create_exam.return_value = MagicMock(exam_id=1, message='Created')
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('create-exam'), self.exam_data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('exam_id', response.data)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    def test_create_exam_grpc_error(self, mock_get_teacher):
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.UNAVAILABLE
        mock_error.details = lambda: 'User service error'
        mock_get_teacher.side_effect = mock_error
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('create-exam'), self.exam_data, format='json')
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['error'], 'User service error')

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    def test_create_exam_grpc_invalid_argument(self, mock_get_teacher):
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.INVALID_ARGUMENT
        mock_error.details = lambda: 'Invalid user ID'
        mock_get_teacher.side_effect = mock_error
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('create-exam'), self.exam_data, format='json')
        self.assertEqual(response.status_code, 502)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    def test_create_exam_grpc_error_details_failure(self, mock_get_teacher):
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.UNAVAILABLE
        mock_error.details = MagicMock(side_effect=Exception('Details failure'))
        mock_get_teacher.side_effect = mock_error
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('create-exam'), self.exam_data, format='json')
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data['error'], 'User service error')
        self.assertTrue(str(mock_error) in response.data['detail'])

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    def test_create_exam_not_teacher(self, mock_get_teacher):
        mock_get_teacher.return_value = MagicMock(teacher_id=0)
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('create-exam'), self.exam_data, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data['error'], 'Only teachers can create exams.')

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    @patch('exams.views.ExamGRPCClient.create_exam')
    def test_create_exam_internal_error(self, mock_create_exam, mock_get_teacher):
        mock_get_teacher.return_value = self.teacher_data
        mock_create_exam.side_effect = Exception('Internal fail')
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('create-exam'), self.exam_data, format='json')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.data['error'], 'Exam creation failed')

    @patch('exams.views.UserGRPCClient')
    def test_create_exam_client_close_error(self, mock_user_client):
        mock_client_instance = MagicMock()
        mock_client_instance.get_teacher_by_user.return_value = self.teacher_data
        mock_client_instance.close.side_effect = Exception('Close failure')
        mock_user_client.return_value = mock_client_instance
        with patch('exams.views.ExamGRPCClient.create_exam') as mock_create_exam:
            mock_create_exam.return_value = MagicMock(exam_id=1, message='Created')
            self.client.force_authenticate(user=self.user_teacher)
            response = self.client.post(reverse('create-exam'), self.exam_data, format='json')
            self.assertEqual(response.status_code, 201)
            mock_client_instance.close.assert_called_once()

    def test_create_exam_invalid_data(self):
        invalid_data = {
            'title': '',  # Invalid: empty title
            'subject': 'Math123',  # Invalid: contains numbers
            'date': '2020-01-01',  # Invalid: past date
            'duration': -10,  # Invalid: negative duration
            'teacher_id': 1
        }
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('create-exam'), invalid_data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('title', response.data)
        self.assertIn('subject', response.data)
        self.assertIn('date', response.data)
        self.assertIn('duration', response.data)

    def test_create_exam_unauthenticated(self):
        response = self.client.post(reverse('create-exam'), self.exam_data, format='json')
        self.assertEqual(response.status_code, 403)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    @patch('exams.views.ExamGRPCClient.list_exams')
    def test_list_exams_success(self, mock_list_exams, mock_get_teacher):
        mock_get_teacher.return_value = self.teacher_data
        mock_exam = MagicMock(exam_id=1, title='Math', subject='Science', date='2025-10-10', duration=90, teacher_id=1)
        mock_list_exams.return_value = MagicMock(exams=[mock_exam])
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.get(reverse('create-exam'))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertGreater(len(response.data), 0)

    @patch('exams.views.ExamGRPCClient.list_exams')
    def test_list_exams_empty(self, mock_list_exams):
        mock_list_exams.return_value = MagicMock(exams=[])
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.get(reverse('create-exam'))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 0)

    @patch('exams.views.ExamGRPCClient.list_exams')
    def test_list_exams_grpc_error(self, mock_list_exams):
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.INVALID_ARGUMENT
        mock_error.details = lambda: 'Invalid argument'
        mock_list_exams.side_effect = mock_error
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.get(reverse('create-exam'))
        self.assertEqual(response.status_code, 400)

    @patch('exams.views.ExamGRPCClient.list_exams')
    def test_list_exams_exception(self, mock_list_exams):
        mock_list_exams.side_effect = Exception('Generic fail')
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.get(reverse('create-exam'))
        self.assertEqual(response.status_code, 500)

    def test_list_exams_unauthenticated(self):
        response = self.client.get(reverse('create-exam'))
        self.assertEqual(response.status_code, 403)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    @patch('exams.views.ExamGRPCClient.assign_exam')
    def test_assign_exam_success(self, mock_assign_exam, mock_get_teacher):
        mock_get_teacher.return_value = self.teacher_data
        mock_assign_exam.return_value = MagicMock(message='Exam assigned successfully')
        exam = Exam.objects.create(**self.exam_data)
        assign_data = {'exam_id': exam.id, 'student_id': [10, 20]}
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('exam-assign'), assign_data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['message'], 'Exam assigned successfully')

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    def test_assign_exam_user_service_error(self, mock_get_teacher):
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.UNAVAILABLE
        mock_error.details = lambda: 'Service down'
        mock_get_teacher.side_effect = mock_error
        exam = Exam.objects.create(**self.exam_data)
        assign_data = {'exam_id': exam.id, 'student_id': [1]}
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('exam-assign'), assign_data, format='json')
        self.assertEqual(response.status_code, 502)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    def test_assign_exam_not_teacher(self, mock_get_teacher):
        mock_get_teacher.return_value = MagicMock(teacher_id=0)
        exam = Exam.objects.create(**self.exam_data)
        assign_data = {'exam_id': exam.id, 'student_id': [1]}
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('exam-assign'), assign_data, format='json')
        self.assertEqual(response.status_code, 403)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    def test_assign_exam_invalid_data(self, mock_get_teacher):
        mock_get_teacher.return_value = self.teacher_data
        assign_data = {'exam_id': '', 'student_id': []}
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('exam-assign'), assign_data, format='json')
        self.assertEqual(response.status_code, 400)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    @patch('exams.views.ExamGRPCClient.assign_exam')
    def test_assign_exam_nonexistent_exam(self, mock_assign_exam, mock_get_teacher):
        mock_get_teacher.return_value = self.teacher_data
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.NOT_FOUND
        mock_error.details = lambda: 'Exam does not exist'
        mock_assign_exam.side_effect = mock_error
        assign_data = {'exam_id': 999, 'student_id': [1]}
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.post(reverse('exam-assign'), assign_data, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Exam does not exist', str(response.data['exam_id'][0]))

    def test_assign_exam_unauthenticated(self):
        exam = Exam.objects.create(**self.exam_data)
        assign_data = {'exam_id': exam.id, 'student_id': [1]}
        response = self.client.post(reverse('exam-assign'), assign_data, format='json')
        self.assertEqual(response.status_code, 403)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    @patch('exams.views.ExamGRPCClient.get_exams_by_teacher')
    def test_teacher_created_exams_success(self, mock_get_exams_by_teacher, mock_get_teacher):
        mock_get_teacher.return_value = self.teacher_data
        mock_exam = MagicMock(exam_id=1, title='Math', subject='Science', date='2025-10-10', duration=90, teacher_id=1)
        mock_get_exams_by_teacher.return_value = MagicMock(exams=[mock_exam])
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.get(reverse('teacher-exams'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('exams', response.data)
        self.assertGreater(len(response.data['exams']), 0)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    @patch('exams.views.ExamGRPCClient.get_exams_by_teacher')
    def test_teacher_created_exams_empty(self, mock_get_exams_by_teacher, mock_get_teacher):
        mock_get_teacher.return_value = self.teacher_data
        mock_get_exams_by_teacher.return_value = MagicMock(exams=[])
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.get(reverse('teacher-exams'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('exams', response.data)
        self.assertEqual(len(response.data['exams']), 0)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    def test_teacher_created_exams_grpc_error(self, mock_get_teacher):
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.UNAVAILABLE
        mock_error.details = lambda: 'User Service error'
        mock_get_teacher.side_effect = mock_error
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.get(reverse('teacher-exams'))
        self.assertEqual(response.status_code, 502)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    def test_teacher_created_exams_not_teacher(self, mock_get_teacher):
        mock_get_teacher.return_value = MagicMock(teacher_id=0)
        self.client.force_authenticate(user=self.user_teacher)
        response = self.client.get(reverse('teacher-exams'))
        self.assertEqual(response.status_code, 403)

    def test_teacher_created_exams_unauthenticated(self):
        response = self.client.get(reverse('teacher-exams'))
        self.assertEqual(response.status_code, 403)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    @patch('exams.views.ExamGRPCClient.get_exams_by_student')
    def test_student_assigned_exams_success(self, mock_get_exams_by_student, mock_get_student):
        ExamAssignment.objects.all().delete()
        mock_get_student.return_value = MagicMock(student=self.student_data)
        mock_exam = MagicMock(exam_id=1, title='Math', subject='Science', date='2025-10-10', duration=90, teacher_id=1)
        mock_get_exams_by_student.return_value = MagicMock(exams=[mock_exam])
        exam = Exam.objects.create(**self.exam_data)
        ExamAssignment.objects.create(exam=exam, student_id=1)
        self.client.force_authenticate(user=self.user_student)
        response = self.client.get(reverse('student-exams'))
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data), 0)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    @patch('exams.views.ExamGRPCClient.get_exams_by_student')
    def test_student_assigned_exams_empty(self, mock_get_exams_by_student, mock_get_student):
        ExamAssignment.objects.all().delete()
        mock_get_student.return_value = MagicMock(student=self.student_data)
        mock_get_exams_by_student.return_value = MagicMock(exams=[])
        self.client.force_authenticate(user=self.user_student)
        response = self.client.get(reverse('student-exams'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 0)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    def test_student_assigned_exams_grpc_error(self, mock_get_student):
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.UNAVAILABLE
        mock_error.details = lambda: 'Student GRPC error'
        mock_get_student.side_effect = mock_error
        self.client.force_authenticate(user=self.user_student)
        response = self.client.get(reverse('student-exams'))
        self.assertEqual(response.status_code, 502)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    def test_student_assigned_exams_not_student(self, mock_get_student):
        mock_get_student.return_value = MagicMock(student=None)
        self.client.force_authenticate(user=self.user_student)
        response = self.client.get(reverse('student-exams'))
        self.assertEqual(response.status_code, 403)

    def test_student_assigned_exams_unauthenticated(self):
        response = self.client.get(reverse('student-exams'))
        self.assertEqual(response.status_code, 403)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    @patch('exams.views.ExamGRPCClient.attempt_exam')
    def test_attempt_exam_success(self, mock_attempt_exam, mock_get_student):
        mock_get_student.return_value = self.student_data
        mock_attempt_exam.return_value = MagicMock(message='Submitted')
        exam = Exam.objects.create(**self.exam_data)
        attempt_data = {'exam_id': exam.id, 'score': 80}
        self.client.force_authenticate(user=self.user_student)
        response = self.client.post(reverse('exam-attempt'), attempt_data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('message', response.data)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    def test_attempt_exam_not_student(self, mock_get_student):
        mock_get_student.return_value = None
        exam = Exam.objects.create(**self.exam_data)
        attempt_data = {'exam_id': exam.id, 'score': 70}
        self.client.force_authenticate(user=self.user_student)
        response = self.client.post(reverse('exam-attempt'), attempt_data, format='json')
        self.assertEqual(response.status_code, 403)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    def test_attempt_exam_missing_fields(self, mock_get_student):
        mock_get_student.return_value = self.student_data
        self.client.force_authenticate(user=self.user_student)
        response = self.client.post(reverse('exam-attempt'), {'score': 70}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('exam_id', response.data)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    @patch('exams.views.ExamGRPCClient.attempt_exam')
    def test_attempt_exam_invalid_exam_id(self, mock_attempt_exam, mock_get_student):
        mock_get_student.return_value = self.student_data
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.NOT_FOUND
        mock_error.details = lambda: 'Exam not found'
        mock_attempt_exam.side_effect = mock_error
        attempt_data = {'exam_id': 999, 'score': 70}
        self.client.force_authenticate(user=self.user_student)
        response = self.client.post(reverse('exam-attempt'), attempt_data, format='json')
        self.assertEqual(response.status_code, 500)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    @patch('exams.views.ExamGRPCClient.attempt_exam')
    def test_attempt_exam_grpc_error(self, mock_attempt_exam, mock_get_student):
        mock_get_student.return_value = self.student_data
        mock_error = grpc.RpcError()
        mock_error.code = lambda: grpc.StatusCode.UNAVAILABLE
        mock_error.details = lambda: 'Exam attempt failed'
        mock_attempt_exam.side_effect = mock_error
        exam = Exam.objects.create(**self.exam_data)
        attempt_data = {'exam_id': exam.id, 'score': 80}
        self.client.force_authenticate(user=self.user_student)
        response = self.client.post(reverse('exam-attempt'), attempt_data, format='json')
        self.assertEqual(response.status_code, 500)

    def test_attempt_exam_unauthenticated(self):
        exam = Exam.objects.create(**self.exam_data)
        attempt_data = {'exam_id': exam.id, 'score': 70}
        response = self.client.post(reverse('exam-attempt'), attempt_data, format='json')
        self.assertEqual(response.status_code, 403)

    @patch('exams.exam_client.grpc.insecure_channel')
    @patch('exams.exam_client.exam_pb2_grpc.ExamServiceStub')
    def test_exam_grpc_client_init(self, mock_stub, mock_channel):
        client = ExamGRPCClient(host='localhost', port=50052)
        mock_channel.assert_called_once_with('localhost:50052', options=[('grpc.keepalive_timeout_ms', 60000)])
        mock_stub.assert_called_once_with(mock_channel.return_value)
        self.assertIsNotNone(client.stub)

    @patch('exams.exam_client.grpc.insecure_channel')
    def test_exam_grpc_client_close(self, mock_channel):
        client = ExamGRPCClient()
        client.close()
        mock_channel.return_value.close.assert_called_once()

    @patch('exams.exam_client.exam_pb2_grpc.ExamServiceStub')
    def test_exam_grpc_client_create_exam(self, mock_stub):
        client = ExamGRPCClient()
        mock_stub_instance = mock_stub.return_value
        mock_stub_instance.CreateExam.return_value = MagicMock(exam_id=1, message='Created')
        result = client.create_exam('Test', 'Math', '2025-10-10', 60, 1)
        mock_stub_instance.CreateExam.assert_called_once()
        self.assertEqual(result.exam_id, 1)
        self.assertEqual(result.message, 'Created')

    @patch('exams.exam_client.exam_pb2_grpc.ExamServiceStub')
    def test_exam_grpc_client_list_exams(self, mock_stub):
        client = ExamGRPCClient()
        mock_stub_instance = mock_stub.return_value
        mock_exam = MagicMock(exam_id=1, title='Math', subject='Science', date='2025-10-10', duration=90, teacher_id=1)
        mock_stub_instance.ListExams.return_value = MagicMock(exams=[mock_exam])
        result = client.list_exams()
        mock_stub_instance.ListExams.assert_called_once()
        self.assertEqual(len(result.exams), 1)
        self.assertEqual(result.exams[0].title, 'Math')

    @patch('exams.exam_client.exam_pb2_grpc.ExamServiceStub')
    def test_exam_grpc_client_get_exam(self, mock_stub):
        client = ExamGRPCClient()
        mock_stub_instance = mock_stub.return_value
        mock_exam = MagicMock(exam_id=1, title='Math', subject='Science', date='2025-10-10', duration=90, teacher_id=1)
        mock_stub_instance.GetExam.return_value = mock_exam
        result = client.get_exam(1)
        mock_stub_instance.GetExam.assert_called_once()
        self.assertEqual(result.exam_id, 1)
        self.assertEqual(result.title, 'Math')

    @patch('exams.exam_client.exam_pb2_grpc.ExamServiceStub')
    def test_exam_grpc_client_assign_exam(self, mock_stub):
        client = ExamGRPCClient()
        mock_stub_instance = mock_stub.return_value
        mock_stub_instance.AssignExam.return_value = MagicMock(message='Exam assigned successfully')
        result = client.assign_exam(1, [1, 2])
        mock_stub_instance.AssignExam.assert_called_once()
        self.assertEqual(result.message, 'Exam assigned successfully')

    @patch('exams.exam_client.exam_pb2_grpc.ExamServiceStub')
    def test_exam_grpc_client_get_exams_by_student(self, mock_stub):
        client = ExamGRPCClient()
        mock_stub_instance = mock_stub.return_value
        mock_exam = MagicMock(exam_id=1, title='Math', subject='Science', date='2025-10-10', duration=90, teacher_id=1)
        mock_stub_instance.GetExamsByStudent.return_value = MagicMock(exams=[mock_exam])
        result = client.get_exams_by_student(1)
        mock_stub_instance.GetExamsByStudent.assert_called_once()
        self.assertEqual(len(result.exams), 1)
        self.assertEqual(result.exams[0].title, 'Math')

    @patch('exams.exam_client.exam_pb2_grpc.ExamServiceStub')
    def test_exam_grpc_client_get_exams_by_teacher(self, mock_stub):
        client = ExamGRPCClient()
        mock_stub_instance = mock_stub.return_value
        mock_exam = MagicMock(exam_id=1, title='Math', subject='Science', date='2025-10-10', duration=90, teacher_id=1)
        mock_stub_instance.GetExamsByTeacher.return_value = MagicMock(exams=[mock_exam])
        result = client.get_exams_by_teacher(1)
        mock_stub_instance.GetExamsByTeacher.assert_called_once()
        self.assertEqual(len(result.exams), 1)
        self.assertEqual(result.exams[0].title, 'Math')

    @patch('exams.exam_client.exam_pb2_grpc.ExamServiceStub')
    def test_exam_grpc_client_attempt_exam(self, mock_stub):
        client = ExamGRPCClient()
        mock_stub_instance = mock_stub.return_value
        mock_stub_instance.AttemptExam.return_value = MagicMock(message='Submitted')
        result = client.attempt_exam(1, 1, 80)
        mock_stub_instance.AttemptExam.assert_called_once()
        self.assertEqual(result.message, 'Submitted')

class ExamServiceTestCase(TestCase):
    def setUp(self):
        self.service = ExamService()
        self.context = MagicMock()

    @patch('exams.grpc_server.Exam.objects.get')
    def test_GetExam_success(self, mock_get):
        mock_exam = MagicMock(id=1, title='Math', subject='Algebra', date=date.today(), duration=60, teacher_id=10)
        mock_get.return_value = mock_exam
        request = MagicMock(exam_id=1)
        response = self.service.GetExam(request, self.context)
        self.assertEqual(response.exam_id, 1)
        self.assertEqual(response.title, 'Math')

    @patch('exams.grpc_server.Exam.objects.all')
    def test_ListExams(self, mock_all):
        exam1 = MagicMock(id=1, title='Math', subject='Algebra', date=date.today(), duration=60, teacher_id=10)
        exam2 = MagicMock(id=2, title='Science', subject='Physics', date=date.today(), duration=90, teacher_id=11)
        mock_all.return_value = [exam1, exam2]
        request = MagicMock()
        response = self.service.ListExams(request, self.context)
        self.assertEqual(len(response.exams), 2)
        self.assertEqual(response.exams[0].title, 'Math')

    @patch('exams.grpc_server.Exam.objects.create')
    def test_CreateExam_success(self, mock_create):
        mock_exam = MagicMock(id=1)
        mock_create.return_value = mock_exam
        request = MagicMock(title='Math', subject='Algebra', date=date.today(), duration=60, teacher_id=10)
        response = self.service.CreateExam(request, self.context)
        self.assertEqual(response.exam_id, 1)
        self.assertEqual(response.message, 'Exam created successfully')

    @patch('exams.grpc_server.Exam.objects.get')
    @patch('exams.grpc_server.ExamAssignment.objects.get_or_create')
    @patch('exams.grpc_server.publish_event')
    def test_AssignExam_success(self, mock_publish, mock_get_or_create, mock_get):
        mock_exam = MagicMock(id=1)
        mock_get.return_value = mock_exam
        request = MagicMock(exam_id=1, student_id=[1, 2, 3])
        response = self.service.AssignExam(request, self.context)
        self.assertIn('Exam assigned to 3 students', response.message)
        mock_publish.assert_called()

    @patch('exams.grpc_server.ExamAssignment.objects.filter')
    @patch('exams.grpc_server.StudentExamAttempt.objects.filter')
    def test_GetExamsByStudent(self, mock_attempt_filter, mock_assign_filter):
        exam1 = MagicMock(id=1, title='Math', subject='Algebra', date=date.today(), duration=60, teacher_id=10)
        assign1 = MagicMock(exam=exam1)
        mock_assign_filter.return_value = [assign1]
        mock_attempt_filter.return_value.values_list.return_value = []
        request = MagicMock(student_id=1)
        response = self.service.GetExamsByStudent(request, self.context)
        self.assertEqual(len(response.exams), 1)
        self.assertEqual(response.exams[0].title, 'Math')

    @patch('exams.grpc_server.Exam.objects.filter')
    def test_GetExamsByTeacher(self, mock_filter):
        exam1 = MagicMock(id=1, title='Math', subject='Algebra', date=date.today(), duration=60, teacher_id=10)
        mock_filter.return_value = [exam1]
        request = MagicMock(teacher_id=10)
        response = self.service.GetExamsByTeacher(request, self.context)
        self.assertEqual(len(response.exams), 1)
        self.assertEqual(response.exams[0].title, 'Math')

    @patch('exams.grpc_server.StudentExamAttempt.objects.filter')
    @patch('exams.grpc_server.Exam.objects.get')
    @patch('exams.grpc_server.StudentExamAttempt.objects.create')
    def test_AttemptExam_success(self, mock_create, mock_get, mock_filter):
        mock_exam = MagicMock(id=1)
        mock_get.return_value = mock_exam
        mock_filter.return_value.exists.return_value = False
        request = MagicMock(exam_id=1, student_id=1, score=95)
        response = self.service.AttemptExam(request, self.context)
        self.assertEqual(response.message, 'Exam submitted successfully')

    @patch('exams.grpc_server.Exam.objects.get')
    def test_AttemptExam_not_found(self, mock_get):
        mock_get.side_effect = Exam.DoesNotExist
        request = MagicMock(exam_id=1, student_id=1, score=95)
        response = self.service.AttemptExam(request, self.context)
        self.context.set_code.assert_called_with(grpc.StatusCode.NOT_FOUND)
        self.context.set_details.assert_called_with('Exam not found')
        self.assertEqual(response.message, 'Exam not found')


if __name__ == '__main__':
    unittest.main()