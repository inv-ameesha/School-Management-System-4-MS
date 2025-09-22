import grpc
from concurrent import futures
import user_service_pb2 as user_service_pb2
import user_service_pb2_grpc as user_pb2_grpc
import django, os

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "user_service.settings")
django.setup()

from .models import Student, Teacher


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

    def GetTeacherByUserId(self, request, context):
        try:
            # Teacher has a OneToOneField to User, Django creates `user_id` FK column
            teacher = Teacher.objects.get(user_id=request.user_id)
            return user_service_pb2.GetTeacherResponse(
                teacher_id=teacher.id,
                first_name=teacher.first_name,
                last_name=teacher.last_name,
                email=teacher.email,
            )
        except Teacher.DoesNotExist:
            # Return a NOT_FOUND status and an empty response (no 'found' field in proto)
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Teacher not found")
            return user_service_pb2.GetTeacherResponse()
        
    def GetStudentByUserId(self, request, context):
        try:
            student = Student.objects.filter(user_id=request.user_id)
            return user_service_pb2.GetStudentByUserResponse(
                student=user_service_pb2.Student(
                    student_id=student.id,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    email=student.email,
                    grade=student.grade if student.grade is not None else 0
                )
            )
        except Student.DoesNotExist:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Student not found")
            return user_service_pb2.GetStudentByUserResponse()
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to fetch student: {str(e)}")
            return user_service_pb2.GetStudentByUserResponse()
        
    def GetStudentsByGradeYear(self, request, context):
        students_data = Student.objects.filter(grade=request.grade, academic_year=request.academic_year)
        
        students_proto = [
            user_service_pb2.Student(
                student_id=s.id,
                first_name=s.first_name,
                last_name=s.last_name,
                email=s.email,
                grade=s.grade,
                academic_year=s.academic_year
            )
            for s in students_data
        ]

        return user_service_pb2.GetStudentsByGradeYearResponse(students=students_proto)

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
