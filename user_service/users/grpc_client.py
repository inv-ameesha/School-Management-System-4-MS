import grpc
from exam_pb2 import ExamRequest, CreateExamRequest , AssignExamRequest , StudentRequest , TeacherRequest
from exam_pb2_grpc import ExamServiceStub
from exam_pb2 import Empty

class ExamGRPCClient:
    def __init__(self, host='127.0.0.1', port=50051):
        options = [('grpc.keepalive_timeout_ms', 60000)]  # 30 seconds timeout
        self.channel = grpc.insecure_channel(f'{host}:{port}', options=options)
        self.stub = ExamServiceStub(self.channel)

    def create_exam(self, title, subject, date, duration, teacher_id):
        request = CreateExamRequest(
            title=title,
            subject=subject,
            date=date,
            duration=duration,
            teacher_id=teacher_id
        )
        response = self.stub.CreateExam(request)
        return response

    def get_exam(self, exam_id):
        response = self.stub.GetExam(ExamRequest(exam_id=exam_id))
        return response

    def list_exams(self): 
        #Empty()- no need of any request to be passed to the server
        response = self.stub.ListExams(Empty())#gets the listexams method from server 
        return response

    def assign_exam(self, exam_id, student_ids):
        request = AssignExamRequest(
            exam_id=exam_id,
            student_ids=student_ids,
        )
        return self.stub.AssignExam(request)

    def get_exams_by_student(self, student_id):
        request = StudentRequest(student_id=student_id)
        return self.stub.GetExamsByStudent(request)

    def get_exams_by_teacher(self, teacher_id):
        request = TeacherRequest(teacher_id=teacher_id)
        return self.stub.GetExamsByTeacher(request)