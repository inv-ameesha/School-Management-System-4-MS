import grpc
from concurrent import futures
import user_service_pb2 as user_service_pb2
import user_service_pb2_grpc as user_pb2_grpc
import django, os

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "user_service.settings")
django.setup()

# Fixed: Use absolute import instead of relative import
from .models import Student, Teacher  # Adjust based on your app structure


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
            teacher = Teacher.objects.get(user_id=request.user_id)
            return user_service_pb2.GetTeacherByUserResponse(  # Fixed: Use correct response type
                found=True,
                teacher=user_service_pb2.Teacher(
                    teacher_id=teacher.id,
                    first_name=teacher.first_name,
                    last_name=teacher.last_name,
                    email=teacher.email,
                )
            )
        except Teacher.DoesNotExist:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Teacher not found")
            return user_service_pb2.GetTeacherByUserResponse(found=False)
        
    def GetStudentByUserId(self, request, context):
        try:
            student = Student.objects.get(user_id=request.user_id)
            return user_service_pb2.GetStudentByUserResponse(
                student=user_service_pb2.Student(
                    student_id=student.id,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    email=student.email,
                    grade=student.grade or 0,
                    academic_year=student.academic_year,
                )
            )
        except Student.DoesNotExist:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Student not found")
            return user_service_pb2.GetStudentByUserResponse()

    def GetStudentById(self, request, context):
        try:
            student = Student.objects.get(id=request.student_id)
            print(f"Found student: {student.first_name} {student.last_name}")
            return user_service_pb2.GetStudentByIdResponse(
                found=True,
                student=user_service_pb2.Student(
                    student_id=student.id,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    email=student.email,
                    grade=student.grade or 0,
                    academic_year=student.academic_year,
                )
            )
            
        except Student.DoesNotExist:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Student not found")
            return user_service_pb2.GetStudentByIdResponse(found=False)

    def GetStudentsByGradeYear(self, request, context):
        try:
            students = Student.objects.filter(
                grade=request.grade,
                academic_year=request.academic_year
            )

            student_messages = []
            for student in students:
                student_messages.append(user_service_pb2.Student(
                    student_id=student.id,
                    first_name=student.first_name,
                    last_name=student.last_name,
                    email=student.email,
                    grade=student.grade,
                    academic_year=student.academic_year,
                ))

            return user_service_pb2.GetStudentsByGradeYearResponse(students=student_messages)

        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to fetch students: {str(e)}")
            return user_service_pb2.GetStudentsByGradeYearResponse()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_pb2_grpc.add_UserServiceServicer_to_server(UserServiceServicer(), server)
    server.add_insecure_port('[::]:50053')
    server.start()
    print("UserService gRPC server running on port 50053...")
    server.wait_for_termination()

if __name__ == "__main__":
    serve()