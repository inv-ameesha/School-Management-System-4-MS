from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import grpc
import logging
from .grpc_client import UserGRPCClient
from .exam_client import ExamGRPCClient
from rest_framework import permissions
from .serializers import ExamSerializer, ExamAssignmentSerializer, StudentExamAttemptSerializer 
from permission import IsStudent, IsTeacher
# logger = logging.getLogger(__name__)

class ExamCreateView(APIView):
    permission_classes = [IsAuthenticated,IsTeacher]

    def post(self, request):
        user = request.user
        user_client = UserGRPCClient(timeout_seconds=5)
        try:
            try:
                teacher_response = user_client.get_teacher_by_user(user.id)
            except grpc.RpcError as e:
                try:
                    details = e.details()#gets the error details
                except Exception:
                    details = str(e)#else stringify the error
                    return Response({"error": "User service error", "detail": details}, status=status.HTTP_502_BAD_GATEWAY)

            #fetch teacher_id from the response , default 0 if not found
            teacher_id = getattr(teacher_response, 'teacher_id', 0)
            if not teacher_id:
                return Response({"error": "Only teachers can create exams."}, status=status.HTTP_403_FORBIDDEN)
        finally:
            try:
                user_client.close()#if method is not found/grpc connection is broken it will raise exception
            except Exception:
                pass

        serializer = ExamSerializer(data=request.data, context={'request': request})
        client = ExamGRPCClient()
        try:
            response = client.create_exam(
                title=serializer.validated_data["title"],
                subject=serializer.validated_data["subject"],
                date=serializer.validated_data["date"],
                duration=serializer.validated_data["duration"],
                teacher_id=teacher_id
            )
            return Response(
                {"exam_id": response.exam_id, "message": response.message},
                status=status.HTTP_201_CREATED
            )
        #handles grpc errors only
        except grpc.RpcError as e:
            return Response(
                {"error": e.details()},
                #HTTP_400_BAD_REQUEST - missing data/invalid format
                #HTTP_500_INTERNAL_SERVER_ERROR - unexpected errors(server crash)
                status=status.HTTP_400_BAD_REQUEST if e.code() == grpc.StatusCode.INVALID_ARGUMENT else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.channel.close()

    def get(self, request):
        client = ExamGRPCClient()
        try:
            response = client.list_exams()
            exams = [
                {
                    "id": exam.exam_id,
                    "title": exam.title,
                    "subject": exam.subject,
                    "date": exam.date,
                    "duration": exam.duration,
                    "teacher_id": exam.teacher_id,
                }
                for exam in response.exams
            ]
            return Response(exams, status=status.HTTP_200_OK)
        except grpc.RpcError as e:
            return Response(
                {"error": e.details()},
                status=status.HTTP_400_BAD_REQUEST if e.code() == grpc.StatusCode.INVALID_ARGUMENT else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.channel.close()

class AssignExamView(APIView):
    permission_classes = [IsAuthenticated,IsStudent]

    def post(self, request):
        user = request.user

        # validate teacher via user service
        user_client = UserGRPCClient(timeout_seconds=5)
        try:
            try:
                teacher_response = user_client.get_teacher_by_user(user.id)
            except grpc.RpcError as e:
                try:
                    details = e.details()
                except Exception:
                    details = str(e)
                return Response({"error": "User service error", "detail": details}, status=status.HTTP_502_BAD_GATEWAY)

            teacher_id = getattr(teacher_response, 'teacher_id', 0)
            if not teacher_id:
                return Response({"error": "Only teachers can assign exams."}, status=status.HTTP_403_FORBIDDEN)
        finally:
            user_client.close()

        serializer = ExamAssignmentSerializer(data=request.data)
        client = ExamGRPCClient()
        try:
            response = client.assign_exam(
                exam_id=serializer.validated_data["exam"].id,
                student_ids=[serializer.validated_data["student"].id],
            )
            return Response({"message": response.message}, status=status.HTTP_201_CREATED)
        except grpc.RpcError as e:
            return Response({"error": e.details()}, status=status.HTTP_400_BAD_REQUEST if e.code() == grpc.StatusCode.INVALID_ARGUMENT else status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.close()


class TeacherCreatedExamsView(APIView):
    permission_classes = [IsAuthenticated,IsTeacher]

    def get(self, request):
        user = request.user
        user_client = UserGRPCClient(timeout_seconds=5)
        try:
            try:
                teacher_response = user_client.get_teacher_by_user(user.id)
            except grpc.RpcError as e:
                return Response(
                    {"error": "User service error", "detail": e.details()},
                    status=status.HTTP_502_BAD_GATEWAY
                )

            teacher_id = getattr(teacher_response, "teacher_id", 0)
            first_name = getattr(teacher_response, "first_name", "")

            if not teacher_id:
                return Response(
                    {"detail": "Only teachers can view their exams."},
                    status=status.HTTP_403_FORBIDDEN
                )
        finally:
            user_client.close()

        client = ExamGRPCClient()
        try:
            response = client.get_exams_by_teacher(teacher_id)
            exams = [
                {
                    "id": exam.exam_id,
                    "title": exam.title,
                    "subject": exam.subject,
                    "date": exam.date,
                    "duration": exam.duration,
                    "teacher_id": exam.teacher_id,
                }
                for exam in response.exams
            ]
            return Response(
                {
                    "teacher_id": teacher_id,
                    "teacher_name": first_name,
                    "exams": exams
                },
                status=status.HTTP_200_OK
            )
        except grpc.RpcError as e:
            return Response(
                {"error": e.details()},
                status=status.HTTP_400_BAD_REQUEST
                if e.code() == grpc.StatusCode.INVALID_ARGUMENT
                else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        finally:
            client.close()

class StudentAssignedExamsView(APIView):
    permission_classes = [IsAuthenticated,IsStudent]

    def get(self, request):
        user = request.user
        user_client = UserGRPCClient(timeout_seconds=5)
        try:
            try:
                student_response = user_client.get_student_by_user(user.id)
            except grpc.RpcError as e:
                return Response({"error": "User service error", "detail": e.details}, status=status.HTTP_502_BAD_GATEWAY)

            #checks whether student_response has student attribute (proto)
            student_msg = getattr(student_response, "student", None)
            student_id = 0
            if student_msg is not None:
                student_id = getattr(student_msg, "student_id", 0)
                first_name = getattr(student_msg, "first_name", "")
            if not student_id:
                return Response({"detail": "Only students can view assigned exams."}, status=status.HTTP_403_FORBIDDEN)
        finally:
            user_client.close()

        client = ExamGRPCClient()
        try:
            response = client.get_exams_by_student(student_id)
            exams = [
                {
                    "id": exam.exam_id,
                    "title": exam.title,
                    "subject": exam.subject,
                    "date": exam.date,
                    "duration": exam.duration,
                    "teacher_id": exam.teacher_id,
                }
                for exam in response.exams#display all exams
            ]
            return Response(
                {
                    "student_id": student_id,
                    "student_name": first_name,
                    "exams": exams
                },
                status=status.HTTP_200_OK
            )
        except grpc.RpcError as e:
            return Response(
                {"error": e.details()},
                status=status.HTTP_400_BAD_REQUEST if e.code() == grpc.StatusCode.INVALID_ARGUMENT else status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.close()

class AttemptExamView(APIView):
    permission_classes = [IsAuthenticated,IsStudent]

    def post(self, request):
        user_id = request.user.id  
        user_client = UserGRPCClient()
        student_response = user_client.get_student_by_user(user_id)

        if not student_response.found:
            return Response(
                {"error": "Only students can attempt exams"},
                status=status.HTTP_403_FORBIDDEN
            )

        student_id = student_response.student_id
        serializer = StudentExamAttemptSerializer(data=request.data)
        exam_id = serializer.validated_data["exam"].id
        score = request.data.get("score")

        if not exam_id or score is None:
            return Response(
                {"error": "exam_id and score are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        client = ExamGRPCClient()
        try:
            response = client.attempt_exam(
                exam_id=int(exam_id),
                student_id=student_id,
                score=float(score)
            )
            return Response({"message": response.message}, status=status.HTTP_200_OK)

        except grpc.RpcError as e:
            return Response(
                {"error": e.details()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )