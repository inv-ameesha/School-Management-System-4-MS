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
import payment_pb2
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

        # Save student instance first
        if user.is_superuser:
            student = serializer.save()
        else:
            teacher = Teacher.objects.filter(user=user).first()
            student = serializer.save(assigned_teacher=teacher)

        try:
            client = PaymentGRPCClient()
            response = client.allocate_fee_for_student(
                student_id=student.id,
                grade=int(student.grade),
                academic_year=student.academic_year
            )
            print(f"[gRPC] Fee allocation response: {response.message}")
        except Exception as e:
            print(f"[gRPC ERROR] Fee allocation failed for student {student.id}: {str(e)}")

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

class ExamCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        if not hasattr(user, "teacher") or user.teacher is None:
            return Response(
                {"error": "Only teachers can create exams."},
                status=status.HTTP_403_FORBIDDEN
            )

        teacher_id = user.teacher.id#teacher table id
        data = request.data
        required_fields = ["title", "subject", "date", "duration"]
        for field in required_fields:
            if not data.get(field):
                return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)


        client = ExamGRPCClient()
        try:
            response = client.create_exam(
                title=data.get("title"),
                subject=data.get("subject"),
                date=data.get("date"),
                duration=data.get("duration"),
                teacher_id=teacher_id
            )
            return Response(
                {"exam_id": response.exam_id, "message": response.message},#server response
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        # finally:
        #     client.channel.close()

    def get(self, request):
        client = ExamGRPCClient()
        try:
            response = client.list_exams()
            exams = []
            for exam in response.exams:
                exams.append({
                    "id": exam.exam_id,
                    "title": exam.title,
                    "subject": exam.subject,
                    "date": exam.date,
                    "duration": exam.duration,
                    "teacher_id": exam.teacher_id,
                })
            return Response(exams, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AssignExamView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        # Only teachers can assign exams
        if not hasattr(user, "teacher") or user.teacher is None:
            return Response(
                {"error": "Only teachers can assign exams."},
                status=status.HTTP_403_FORBIDDEN
            )

        exam_id = request.data.get("exam_id")
        student_ids = request.data.get("student_ids")  # expected list of IDs

        if not exam_id or not isinstance(student_ids, list) or not student_ids:#not list or empty list
            return Response(
                {"error": "exam_id and student_ids (list) are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        client = ExamGRPCClient()
        try:
            response = client.assign_exam(exam_id=exam_id, student_ids=student_ids)
            return Response({"message": response.message}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StudentAssignedExamsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "student"):
            return Response({"detail": "Only students can view assigned exams."}, status=403)

        student_id = request.user.student.id
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
                    "teacher_id": exam.teacher_id
                }
                for exam in response.exams
            ]
            return Response(exams, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class TeacherCreatedExamsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "teacher"):
            return Response({"detail": "Only teachers can view their exams."}, status=403)

        teacher_id = request.user.teacher.id
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
                    "teacher_id": exam.teacher_id
                }
                for exam in response.exams
            ]
            return Response(exams, status=200)
        except Exception as e:
            return Response({"error": str(e)}, status=500)

class FeeAllocationView(APIView):
    permission_classes = [permissions.IsAdminUser]  # only admin can allocate fee

    def post(self, request):
        # Extract raw data directly from request
        data = request.data  

        # Validate required fields manually
        required_fields = ["grade", "academic_year", "base_fee", "due_date", "fine_per_day"]
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            return Response(
                {"error": f"Missing required fields: {', '.join(missing)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        client = PaymentGRPCClient()
        try:
            response = client.allocate_fee(
                grade=data.get("grade"),
                academic_year=data.get("academic_year"),
                base_fee = float(data.get("base_fee")), 
                due_date=data.get("due_date"),  # ensure date format matches model (yyyy-mm-dd)
                fine_per_day = float(data.get("fine_per_day")),
            )
            return Response(
                {"message": response.message},
                status=status.HTTP_201_CREATED
            )
        except (ValueError, TypeError):
            return Response({"error": "Invalid input"}, status=400)
        except grpc.RpcError:
            return Response({"error": "Service unavailable"}, status=502)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        student_fee_id = request.data.get("student_fee_id")
        gateway = request.data.get("gateway")
        print("hi")
        if not student_fee_id or not gateway:
            return Response(
                {"error": "student_fee_id and gateway are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # print("User:", request.user)
        # print("Is student:", hasattr(request.user, "student"))
        client = PaymentGRPCClient()
        try:
            response = client.initiate_payment(
                student_fee_id=int(student_fee_id),
                student_id=request.user.student.id,
                gateway=gateway,
            )
            return Response(
                {
                    "message": response.message,
                    "payment_id": response.payment_id,
                    "order_id": response.order_id,
                    "amount": response.amount,
                    "currency": response.currency,
                },
                status=status.HTTP_200_OK,
                
            )
        except grpc.RpcError as e:
            return Response(
                {"error": e.details()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

class SimulateRazorpayPaymentView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        payment_id = request.data.get("payment_id")
        razorpay_order_id = request.data.get("razorpay_order_id")

        if not payment_id or not razorpay_order_id:
            return Response(
                {"error": "payment_id and razorpay_order_id are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        client = PaymentGRPCClient()
        try:
            response = client.simulate_razorpay_payment(
                payment_id=int(payment_id),
                razorpay_order_id=razorpay_order_id
            )
            return Response({
                "payment_id": response.payment_id,
                "razorpay_order_id": response.razorpay_order_id,
                "razorpay_payment_id": response.razorpay_payment_id,
                "razorpay_signature": response.razorpay_signature
            }, status=status.HTTP_200_OK)

        except grpc.RpcError as e:
            return Response(
                {"error": e.details()},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class VerifyRazorpayPaymentView(APIView):
    permission_classes = [IsAuthenticated, IsStudent]

    def post(self, request):
        payment_id = request.data.get("payment_id")
        razorpay_order_id = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature = request.data.get("razorpay_signature")

        if not all([payment_id, razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        client = PaymentGRPCClient()
        try:
            response = client.verify_payment(
                payment_id=int(payment_id),
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature
            )

            if response.message != "Payment verified successfully":
                return Response({"error": response.message}, status=status.HTTP_400_BAD_REQUEST)

            student = request.user.student
            receipt_response = client.generate_receipt(
                payment_id=int(payment_id),
                student=student
            )

            return Response(
                {
                    "message": receipt_response.message,
                    "receipt_url": receipt_response.receipt_url
                },
                status=status.HTTP_200_OK
            )

        except grpc.RpcError as e:
            return Response({"error": e.details()}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AttemptExamView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if not hasattr(user, "student"):
            return Response({"error": "Only students can attempt exams"}, status=403)

        exam_id = request.data.get("exam_id")
        score = request.data.get("score")

        if not exam_id or score is None:
            return Response({"error": "exam_id and score are required"}, status=400)

        client = ExamGRPCClient()
        try:
            response = client.attempt_exam(
                exam_id=int(exam_id),
                student_id=user.student.id,
                score=float(score)
            )
            return Response({"message": response.message}, status=200)

        except grpc.RpcError as e:
            return Response({"error": e.details()}, status=500)

class TransactionLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            client = PaymentGRPCClient()
            response = client.list_logs()

            logs = [
                {
                    "id": log.id,
                    "log_message": log.log_message,
                    "log_type": log.log_type,
                    "created_at": log.created_at,
                }
                for log in response.logs
            ]
            return Response(logs, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Failed to fetch logs: {str(e)}"}, status=500)
