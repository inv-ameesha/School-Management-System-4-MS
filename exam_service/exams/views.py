from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import grpc
from .grpc_client import UserGRPCClient
from .exam_client import ExamGRPCClient

class ExamCreateView(APIView):
    print("ExamCreateView initialized")
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        user_client = UserGRPCClient()

        teacher_response = user_client.get_teacher_by_user(user.id)
        if not teacher_response.found:
            return Response(
                {"error": "Only teachers can create exams."},
                status=status.HTTP_403_FORBIDDEN
            )

        teacher_id = teacher_response.teacher_id
        data = request.data

        required_fields = ["title", "subject", "date", "duration"]
        for field in required_fields:
            if not data.get(field):
                return Response(
                    {"error": f"{field} is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        client = ExamGRPCClient()
        try:
            response = client.create_exam(
                title=data["title"],
                subject=data["subject"],
                date=data["date"],
                duration=data["duration"],
                teacher_id=teacher_id
            )
            return Response(
                {"exam_id": response.exam_id, "message": response.message},
                status=status.HTTP_201_CREATED
            )
        except grpc.RpcError as e:
            return Response(
                {"error": e.details()},
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
