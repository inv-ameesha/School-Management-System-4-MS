from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
from .models import Exam, ExamAssignment, StudentExamAttempt
from datetime import date
from django.contrib.auth.models import User
import grpc

class ExamViewsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.user.teacher = type('obj', (object,), {'id': 1})()  # Mock teacher attribute
        self.user.student = type('obj', (object,), {'id': 1})()  # Mock student attribute
        self.client.force_authenticate(user=self.user)  # Authenticate user
        self.teacher_data = {
            'teacher_id': 1,
            'first_name': 'Teacher',
            'user_id': self.user.id
        }
        self.student_data = {
            'student_id': 1,
            'first_name': 'Student',
            'user_id': self.user.id
        }
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
        mock_get_teacher.return_value = type('obj', (object,), self.teacher_data)()
        mock_create_exam.return_value = type('obj', (object,), {'exam_id': 1, 'message': 'Exam created successfully'})()
        response = self.client.post(reverse('create-exam'), self.exam_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('exam_id', response.data)
        self.assertEqual(response.data['message'], 'Exam created successfully')

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    @patch('exams.views.ExamGRPCClient.assign_exam')
    def test_assign_exam_success(self, mock_assign_exam, mock_get_teacher):
        mock_get_teacher.return_value = type('obj', (object,), self.teacher_data)()
        mock_assign_exam.return_value = type('obj', (object,), {'message': 'Exam assigned to 1 students.'})()
        exam = Exam.objects.create(**self.exam_data)
        assign_data = {
            'exam_id': exam.id,
            'student_id': [1]
        }
        response = self.client.post(reverse('exam-assign'), assign_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)

    @patch('exams.views.UserGRPCClient.get_teacher_by_user')
    @patch('exams.views.ExamGRPCClient.get_exams_by_teacher')
    def test_teacher_created_exams(self, mock_get_exams_by_teacher, mock_get_teacher):
        mock_get_teacher.return_value = type('obj', (object,), self.teacher_data)()
        mock_exam = type('obj', (object,), {
            'exam_id': 1,
            'title': 'Test Exam',
            'subject': 'Math',
            'date': '2025-10-10',
            'duration': 60,
            'teacher_id': 1
        })()
        mock_get_exams_by_teacher.return_value = type('obj', (object,), {'exams': [mock_exam]})()
        Exam.objects.create(**self.exam_data)
        response = self.client.get(reverse('teacher-exams'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('exams', response.data)
        self.assertEqual(response.data['teacher_id'], 1)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    @patch('exams.views.ExamGRPCClient.get_exams_by_student')
    def test_student_assigned_exams(self, mock_get_exams_by_student, mock_get_student):
        mock_get_student.return_value = type('obj', (object,), {
            'student': type('obj', (object,), self.student_data)()
        })()
        mock_exam = type('obj', (object,), {
            'exam_id': 1,
            'title': 'Test Exam',
            'subject': 'Math',
            'date': '2025-10-10',
            'duration': 60,
            'teacher_id': 1
        })()
        mock_get_exams_by_student.return_value = type('obj', (object,), {'exams': [mock_exam]})()
        exam = Exam.objects.create(**self.exam_data)
        ExamAssignment.objects.create(exam=exam, student_id=1)
        response = self.client.get(reverse('student-exams'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('exams', response.data)
        self.assertEqual(response.data['student_id'], 1)

    @patch('exams.views.UserGRPCClient.get_student_by_user')
    @patch('exams.views.ExamGRPCClient.attempt_exam')
    def test_attempt_exam_success(self, mock_attempt_exam, mock_get_student):
        mock_get_student.return_value = type('obj', (object,), {
            'student': type('obj', (object,), self.student_data)()
        })()
        mock_attempt_exam.return_value = type('obj', (object,), {'message': 'Exam submitted successfully'})()
        exam = Exam.objects.create(**self.exam_data)
        attempt_data = {
            'exam_id': exam.id,
            'score': 85
        }
        response = self.client.post(reverse('exam-attempt'), attempt_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)