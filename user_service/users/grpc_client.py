import grpc
from exam_pb2 import ExamRequest, CreateExamRequest
from exam_pb2_grpc import ExamServiceStub

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

if __name__ == "__main__":
    try:
        client = ExamGRPCClient()
        # import time
        # time.sleep(5) 
        created = client.create_exam(
            title="English Test",
            subject="Propositions",
            date="2025-09-15",
            duration=60,
            teacher_id=1
        )
        print(f"Created Exam: ID={created.exam_id}, Message={created.message}")

        exam = client.get_exam(exam_id=created.exam_id)
        print(
            f"Exam Details -> ID: {exam.exam_id}, "
            f"Title: {exam.title}, Subject: {exam.subject}, "
            f"Date: {exam.date}, Duration: {exam.duration}, "
            f"Teacher ID: {exam.teacher_id}"
        )
    except Exception as e:
        print(f"Error: {e}")