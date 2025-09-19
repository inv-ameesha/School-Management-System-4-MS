import grpc
from concurrent import futures
import user_service_pb2 as user_service_pb2
import user_service_pb2_grpc as user_pb2_grpc
import django, os

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "user_service.settings")
django.setup()

from .models import Student,Teacher

class UserServiceServicer(user_pb2_grpc.UserServiceServicer):
    def GetStudentsByIds(self, request, context):
        try:
            students = Student.objects.filter(id__in=request.student_ids)
            return user_service_pb2.GetStudentsResponse(
                students=[
                    user_service_pb2.Student(
                        student_id=s.id,
                        first_name=s.first_name,
                        last_name=s.last_name,
                        email=s.email,
                        grade=s.grade
                    )
                    for s in students
                ]
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to fetch students: {str(e)}")
            return user_service_pb2.GetStudentsResponse()
        
class UserServiceServicer(user_pb2_grpc.UserServiceServicer):
    def GetTeacherByUserId(self, request, context):
        try:
            teacher = Teacher.objects.get(user_id=request.user_id)
            return user_service_pb2.GetTeacherResponse(
                # found=True,
                teacher_id=teacher.id,
                first_name=teacher.first_name,
                last_name=teacher.last_name,
                email=teacher.email
            )
        except Teacher.DoesNotExist:
            return user_service_pb2.GetTeacherResponse(found=False)

def serve():
    #creates grpc server instance with a thread pool of 10 workers
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    #helper function links the servicer class to the server
    user_pb2_grpc.add_UserServiceServicer_to_server(UserServiceServicer(), server)
    server.add_insecure_port('[::]:50053')#connection to port 50053
    server.start()
    print("UserService gRPC server running on port 50053...")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()
