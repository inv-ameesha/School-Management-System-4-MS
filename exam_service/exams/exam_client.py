import grpc
from exam_pb2 import CreateExamRequest
from exam_pb2_grpc import ExamServiceStub

class ExamGRPCClient:
    def __init__(self, host='127.0.0.1', port=50051):
        options = [('grpc.keepalive_timeout_ms', 60000)] 
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
        return self.stub.CreateExam(request)