from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView  
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Teacher, Student
from .serializers import TeacherSerializer, StudentSerializer,CustomTokenObtainPairSerializer
from .permissions import IsTeacher
from django.contrib.auth.models import User
from rest_framework.exceptions import AuthenticationFailed
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser
from rest_framework import status
from rest_framework import permissions
from django.db import transaction
import csv
from io import TextIOWrapper
from .grpc_client import ExamGRPCClient
from .payment_client import PaymentGRPCClient
from django.utils import timezone
from .permissions import IsStudent
import grpc
import pika
import json
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
#viewset : allows multiple views within a single class
class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.all()#get the teacher data
    serializer_class = TeacherSerializer

    def get_permissions(self):
        if self.action == 'me':
            return [IsTeacher()]#if url=me only teacher could access
        return [IsAdminUser()]#else admins also could access;IsAdminUser-inbuilt
    #detail=False : action operates on a list of object not on a single object
    @action(detail=False, methods=['get'], url_path='me', permission_classes=[IsTeacher])
    def me(self, request):
        teacher = Teacher.objects.filter(user=request.user).first()#gets the teacher object of the loged in teacher
        if not teacher:
            return Response({'detail': 'No teacher profile found for this user.'}, status=404)
        serializer = self.get_serializer(teacher)#serializes the obtained data
        return Response(serializer.data)

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAdminUser]  # Only admin can do anything

    def perform_create(self, serializer):
        student = serializer.save()

        # Publish message to RabbitMQ instead of calling gRPC directly
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            channel = connection.channel()
            channel.queue_declare(queue='student_fee_queue', durable=True)

            message = {
                "student_id": student.id,
                "grade": student.grade,
                "academic_year": student.academic_year,
            }

            channel.basic_publish(
                exchange='',#by default direct
                routing_key='student_fee_queue',
                body=json.dumps(message),
                properties=pika.BasicProperties(delivery_mode=2)  # persistent msg
            )
            connection.close()

            print(f"[RabbitMQ] Published student {student.id} for fee allocation.")
        except Exception as e:
            print(f"[RabbitMQ ERROR] Failed to publish student {student.id}: {str(e)}")

    def destroy(self, request, *args, **kwargs):
        student = self.get_object()
        student.status = 'Inactive'

        tag = str(datetime.now().timestamp())
        student.email = student.email.replace("@", f"{tag}@")
        student.save()

        return Response({"detail": "Student soft-deleted."}, status=status.HTTP_202_ACCEPTED)

class ImportStudentsCSV(APIView):
    parser_classes = [MultiPartParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        csv_file = request.FILES.get("file")

        if not csv_file or not csv_file.name.endswith(".csv"):
            return Response(
                {"error": "Invalid file format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        data_set = TextIOWrapper(csv_file.file, encoding="utf-8")#converts the file into a text stream
        csv_reader = csv.DictReader(data_set)#saves the data in dict format like key-value pair

        created, errors = 0, []
        is_admin = request.user.is_staff
        is_teacher = hasattr(request.user, "teacher")

        for i, row in enumerate(csv_reader, start=1):
            try:

                if User.objects.filter(username=row.get("username")).exists():
                    errors.append(f"Row {i}: Username {row['username']} already exists")
                    continue
                if Student.objects.filter(roll_number=row.get("roll_number")).exists():
                    errors.append(f"Row {i}: Roll number {row['roll_number']} already exists")
                    continue
                if Student.objects.filter(email=row.get("email")).exists():
                    errors.append(f"Row {i}: Email {row['email']} already exists")
                    continue

                teacher = None
                if is_admin and row.get("assigned_teacher_id"):
                    try:
                        teacher = Teacher.objects.get(id=row["assigned_teacher_id"])
                    except Teacher.DoesNotExist:
                        errors.append(
                            f"Row {i}: Teacher with ID {row['assigned_teacher_id']} not found"
                        )
                        continue
                # elif is_teacher:
                #     teacher = request.user.teacher

                with transaction.atomic():
                    # Create user
                    # user = User.objects.create_user(
                    #     username=row["username"],
                    #     password=row["password"],
                    #     email=row["email"]
                    # )

                    # Prepare student data
                    student_data = {
                        "username": row.get("username"),
                        "password": row.get("password"),
                        "email": row.get("email"),
                        "first_name": row.get("first_name"),
                        "last_name": row.get("last_name"),
                        "phone_number": row.get("phone_number"),
                        "roll_number": row.get("roll_number"),
                        "grade": row.get("grade") or None,
                        "academic_year": row.get("academic_year") or None,
                        "date_of_birth": row.get("date_of_birth"),
                        "admission_date": row.get("admission_date"),
                        "status": row.get("status"),
                        "assigned_teacher": teacher.id if teacher else None,
                    }
                    serializer = StudentSerializer(data=student_data)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()

                    created += 1 #used down

            except Exception as e:
                errors.append(f"Row {i}: {str(e)}")

        return Response(
            {
                "message": f"{created} students imported successfully",
                "errors": errors,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST,
        )
