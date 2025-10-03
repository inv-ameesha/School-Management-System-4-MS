import grpc
import exam_pb2 as pb
from exam_pb2_grpc import ExamServiceStub


class ExamGRPCClient:
    def __init__(self, host='127.0.0.1', port=50051):
        options = [('grpc.keepalive_timeout_ms', 60000)]
        self.channel = grpc.insecure_channel(f'{host}:{port}', options=options)
        self.stub = ExamServiceStub(self.channel)

    def create_exam(self, title, subject, date, duration, teacher_id):
        request = pb.CreateExamRequest(
            title=title,
            subject=subject,
            date=date,
            duration=duration,
            teacher_id=teacher_id
        )
        return self.stub.CreateExam(request)

    def list_exams(self):
        return self.stub.ListExams(pb.Empty())

    def get_exam(self, exam_id):
        return self.stub.GetExam(pb.ExamRequest(exam_id=exam_id))

    def assign_exam(self, exam_id, student_id):
        request = pb.AssignExamRequest(exam_id=int(exam_id), student_id=student_id)
        return self.stub.AssignExam(request)

    def get_exams_by_student(self, student_id):
        return self.stub.GetExamsByStudent(pb.StudentRequest(student_id=int(student_id)))

    def get_exams_by_teacher(self, teacher_id):
        return self.stub.GetExamsByTeacher(pb.TeacherRequest(teacher_id=int(teacher_id)))

    def attempt_exam(self, exam_id, student_id, score):
        request = pb.AttemptExamRequest(exam_id=int(exam_id), student_id=int(student_id), score=int(score))
        return self.stub.AttemptExam(request)

    def close(self):
        self.channel.close()
