import grpc
import user_service_pb2
import user_service_pb2_grpc


class UserGRPCClient:
    def __init__(self, host="localhost", port=50053, timeout_seconds=None):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = user_service_pb2_grpc.UserServiceStub(self.channel)
        self.timeout = timeout_seconds

    def close(self):
        self.channel.close()

    def get_teacher_by_user(self, user_id):
        request = user_service_pb2.GetTeacherRequest(user_id=int(user_id))
        if self.timeout is not None:
            return self.stub.GetTeacherByUserId(request, timeout=self.timeout)
        return self.stub.GetTeacherByUserId(request)

    def get_student_by_user(self, user_id):
        request = user_service_pb2.GetStudentByUserRequest(user_id=int(user_id))
        if self.timeout is not None:
            return self.stub.GetStudentByUserId(request, timeout=self.timeout)
        return self.stub.GetStudentByUserId(request)

