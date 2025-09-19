import grpc
import user_service_pb2
import user_service_pb2_grpc


class UserGRPCClient:
    def __init__(self, host="localhost", port=50053):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = user_service_pb2_grpc.UserServiceStub(self.channel)

    def get_teacher_by_user(self, user_id):
        request = user_service_pb2.GetTeacherRequest(user_id=user_id)
        return self.stub.GetTeacherByUserId(request)

