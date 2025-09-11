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
    serializer_class = StudentSerializer
    queryset = Student.objects.all()

    def get_permissions(self):#self:instance of that cls for actions like self.request,self.action etc
        user = self.request.user
        if self.action == 'me':
            return [IsAuthenticated()]
        if self.request.method == 'GET':
            if user.is_superuser:
                return [IsAdminUser()]
            elif Student.objects.filter(user=user).exists():
                return [IsAuthenticated()]  # Allow student to access own details
            else:
                return [IsTeacher()]
        if self.request.method == 'POST':
            return [IsAdminUser()] if user.is_superuser else [IsTeacher()]
        if self.request.method in ['PUT', 'PATCH']:
            return [IsAdminUser()] if user.is_superuser else [IsTeacher()]
        if self.request.method == 'DELETE':
            return [IsAdminUser()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Student.objects.all()
        elif Teacher.objects.filter(user=user).exists():
            teacher = Teacher.objects.get(user=user)
            return Student.objects.filter(assigned_teacher=teacher)
        elif Student.objects.filter(user=user).exists():
            student = Student.objects.get(user=user)
            return Student.objects.filter(id=student.id)
        else:
            return Student.objects.none()
        return Student.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_superuser:
            serializer.save()
        else:
            teacher = Teacher.objects.filter(user=user).first()
            serializer.save(assigned_teacher=teacher)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user

        if user.is_superuser:
            return super().retrieve(request, *args, **kwargs)

        if Teacher.objects.filter(user=user).exists():
            teacher = Teacher.objects.get(user=user)
            if instance.assigned_teacher == teacher:
                return super().retrieve(request, *args, **kwargs)
            return Response({"detail": "You do not have permission to access this student."}, status=403)

        if Student.objects.filter(user=user).exists():
            student = Student.objects.get(user=user)
            if instance.id == student.id:
                return super().retrieve(request, *args, **kwargs)
            return Response({"detail": "You do not have permission to access this student."}, status=403)

        return Response({"detail": "Permission denied."}, status=403)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        user = request.user

        if user.is_superuser:
            return super().update(request, *args, **kwargs)

        if Teacher.objects.filter(user=user).exists():
            teacher = Teacher.objects.get(user=user)
            if instance.assigned_teacher == teacher:
                return super().update(request, *args, **kwargs)
            return Response({"detail": "You do not have permission to edit this student."}, status=403)

        return Response({"detail": "Permission denied."}, status=403)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response({"detail": "Only admin can delete students."}, status=403)
        student = Student.objects.get(pk=kwargs['pk'])
        student.status = 'Inactive'
        email_address = student.email
        tag = str(datetime.now())
        new_email_address = email_address.replace("@", tag + "@")
        student.email=new_email_address
        print(new_email_address)
        student.save()
        return Response({"detail": "deleted."}, status=202)

    @action(detail=False, methods=['get'], url_path='me', permission_classes=[IsAuthenticated])
    def me(self, request):
        student = Student.objects.filter(user=request.user).first()
        if not student:
            return Response({'detail': 'Student profile not found'}, status=404)
        serializer = self.get_serializer(student)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by-teacher/(?P<teacher_id>[^/.]+)')
    def by_teacher(self, request, teacher_id=None):
        if not request.user.is_superuser:
            return Response({'detail': 'Permission denied'}, status=403)
        students = Student.objects.filter(assigned_teacher_id=teacher_id)
        serializer = self.get_serializer(students, many=True)
        return Response(serializer.data)

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


