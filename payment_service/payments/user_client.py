import grpc
import user_service_pb2
import user_service_pb2_grpc

class UserGRPCClient:
    def __init__(self, host="127.0.0.1", port=50053):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = user_service_pb2_grpc.UserServiceStub(self.channel)

    def get_students_by_grade_year(self, grade, academic_year):
        request = user_service_pb2.GetStudentsByGradeYearRequest(
            grade=int(grade),
            academic_year=academic_year
        )
        response = self.stub.GetStudentsByGradeYear(request)
        return response.students

    def get_teacher_by_user(self, user_id):
        request = user_service_pb2.GetTeacherRequest(user_id=int(user_id))
        try:
            return self.stub.GetTeacherByUserId(request)
        except grpc.RpcError as e:
            raise e

    def get_student_by_user(self, user_id):
        request = user_service_pb2.GetStudentsRequest(user_id=[int(user_id)])
        try:
            return self.stub.GetStudentByUserId(request)
        except grpc.RpcError as e:
            raise e
        
    def close(self):
        self.channel.close()
