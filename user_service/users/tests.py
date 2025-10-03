import csv
import io
from django.forms import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from datetime import date
from django.core.files.uploadedfile import SimpleUploadedFile
from .serializers import CustomTokenObtainPairSerializer, StudentSerializer, TeacherSerializer

from .payment_client import PaymentGRPCClient
from .models import Student, Teacher

class StudentViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(username="admin", password="adminpass", email="admin@example.com")
        self.client.force_authenticate(user=self.admin_user)

        self.teacher_user = User.objects.create_user(username="teacher1", password="pass123")
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            first_name="Test",
            last_name="Teacher",
            email="teacher@example.com",
            phone=1234567890,
            subject="Math",
            e_id="T001",
            doj=date.today(),
            status="Active"
        )

    @patch("users.views.pika.BlockingConnection")
    def test_student_create_and_rabbitmq_publish(self, mock_pika_connection):
        mock_channel = MagicMock()
        mock_pika_connection.return_value.channel.return_value = mock_channel

        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "username": "john_doe",           
            "password": "securepass123",      
            "email": "john@example.com",      
            "phone_number": "1234567890",
            "roll_number": "R001",
            "grade": 5,
            "academic_year": "2025-2026",
            "date_of_birth": "2010-01-01",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher": self.teacher.id
        }

        response = self.client.post("/api/students/", payload, format='json')
        self.assertEqual(response.status_code, 201)

        student = Student.objects.get(email="john@example.com")
        self.assertEqual(student.first_name, "John")
        self.assertEqual(student.assigned_teacher.id, self.teacher.id)

        mock_channel.queue_declare.assert_called_once_with(queue='student_fee_queue', durable=True)
        self.assertTrue(mock_channel.basic_publish.called)

    def test_student_create_duplicate_username(self):
        payload1 = {
            "first_name": "Jake",
            "last_name": "Long",
            "username": "john_doe", 
            "password": "securepass123",
            "email": "unique1@example.com",
            "phone_number": "1234567890",
            "roll_number": "R100",  
            "grade": 7,
            "academic_year": "2025-2026",
            "date_of_birth": "2010-03-03",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher": self.teacher.id
        }
        self.client.post("/api/students/", payload1, format='json')

        payload2 = payload1.copy()
        payload2["email"] = "unique2@example.com"    
        payload2["roll_number"] = "R101"              
        response = self.client.post("/api/students/", payload2, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data) 

    def test_student_create_duplicate_email(self):
        Student.objects.create(
            user=User.objects.create_user(username="s1", password="pass", email="dup@example.com"),
            first_name="Existing",
            last_name="User",
            email="dup@example.com",
            phone_number="1111111111",
            roll_number="R010",
            grade=9,
            academic_year="2025-2026",
            date_of_birth="2010-04-04",
            admission_date="2020-06-01",
            status="Active",
            assigned_teacher=self.teacher
        )

        payload = {
            "first_name": "Dup",
            "last_name": "Check",
            "username": "dupuser",
            "password": "securepass123",
            "email": "dup@example.com",  
            "phone_number": "2222222222",
            "roll_number": "R011",
            "grade": 9,
            "academic_year": "2025-2026",
            "date_of_birth": "2010-05-05",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher": self.teacher.id
        }

        response = self.client.post("/api/students/", payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_student_create_duplicate_roll_number(self):
        Student.objects.create(
            user=User.objects.create_user(username="s2", password="pass", email="roll@example.com"),
            first_name="Roll",
            last_name="One",
            email="roll@example.com",
            phone_number="3333333333",
            roll_number="R100",
            grade=8,
            academic_year="2025-2026",
            date_of_birth="2010-06-06",
            admission_date="2020-06-01",
            status="Active",
            assigned_teacher=self.teacher
        )

        payload = {
            "first_name": "Roll",
            "last_name": "Dup",
            "username": "rolluser",
            "password": "securepass123",
            "email": "rollnew@example.com",
            "phone_number": "4444444444",
            "roll_number": "R100",  
            "grade": 8,
            "academic_year": "2025-2026",
            "date_of_birth": "2010-07-07",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher": self.teacher.id
        }

        response = self.client.post("/api/students/", payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("roll_number", response.data)

    def test_student_list(self):
        for i in range(3):
            user = User.objects.create_user(username=f"student{i}", password="pass")
            Student.objects.create(
                user=user,
                first_name=f"First{i}",
                last_name=f"Last{i}",
                email=f"s{i}@example.com",
                phone_number="1234567890",
                roll_number=f"R10{i}",
                grade=5,
                academic_year="2025-2026",
                date_of_birth="2010-01-01",
                admission_date="2020-06-01",
                status="Active",
                assigned_teacher=self.teacher
            )

        response = self.client.get("/api/students/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)
    
    def test_student_retrieve(self):
        user = User.objects.create_user(username="studentX", password="pass")
        student = Student.objects.create(
            user=user,
            first_name="Retrieve",
            last_name="Test",
            email="retrieve@example.com",
            phone_number="1234567890",
            roll_number="R200",
            grade=5,
            academic_year="2025-2026",
            date_of_birth="2010-01-01",
            admission_date="2020-06-01",
            status="Active",
            assigned_teacher=self.teacher
        )

        response = self.client.get(f"/api/students/{student.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["first_name"], "Retrieve")

    def test_student_update(self):
        user = User.objects.create_user(username="updatetest", password="pass")
        student = Student.objects.create(
            user=user,
            first_name="OldName",
            last_name="OldLast",
            email="update@example.com",
            phone_number="1234567890",
            roll_number="R300",
            grade=5,
            academic_year="2025-2026",
            date_of_birth="2010-01-01",
            admission_date="2020-06-01",
            status="Active",
            assigned_teacher=self.teacher
        )

        payload = {"first_name": "NewName", "grade": 6}
        response = self.client.patch(f"/api/students/{student.id}/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        student.refresh_from_db()
        self.assertEqual(student.first_name, "NewName")
        self.assertEqual(student.grade, 6)

    def test_student_create_missing_first_name(self):
        payload = {
            # "first_name" is missing
            "last_name": "MissingFirst",
            "username": "missingfirst",
            "password": "pass123",
            "email": "missing@example.com",
            "phone_number": "1234567890",
            "roll_number": "R400",
            "grade": 5,
            "academic_year": "2025-2026",
            "date_of_birth": "2010-01-01",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher": None  # optional, can be missing
        }
        response = self.client.post("/api/students/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("first_name", response.data)

    def test_student_create_non_admin(self):
        teacher_user = User.objects.create_user(username="teacher2", password="pass")
        self.client.force_authenticate(user=teacher_user)

        payload = {
            "first_name": "Unauthorized",
            "last_name": "User",
            "username": "unauthuser",
            "password": "pass123",
            "email": "unauth@example.com",
            "phone_number": "1234567890",
            "roll_number": "R500",
            "grade": 5,
            "academic_year": "2025-2026",
            "date_of_birth": "2010-01-01",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher": self.teacher.id
        }

        response = self.client.post("/api/students/", payload, format="json")
        self.assertIn(response.status_code, [403, 401])

    def test_student_create_invalid_grade_type(self):
        payload = {
            "first_name": "Invalid",
            "last_name": "Grade",
            "username": "invalidgrade",
            "password": "pass123",
            "email": "invalidgrade@example.com",
            "phone_number": "1234567890",
            "roll_number": "R501",
            "grade": "five", 
            "academic_year": "2025-2026",
            "date_of_birth": "2010-01-01",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher": self.teacher.id
        }
        response = self.client.post("/api/students/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("grade", response.data)

    def test_student_soft_delete(self):
        student_user = User.objects.create_user(username="student1", password="pass123")
        student = Student.objects.create(
            user=student_user,
            first_name="Alice",
            last_name="Smith",
            email="alice@example.com",
            phone_number="1234567890",
            roll_number="R002",
            grade=6,
            academic_year="2025-2026",
            date_of_birth="2010-02-02",
            admission_date="2020-06-01",
            status="Active",
            assigned_teacher=self.teacher
        )

        response = self.client.delete(f"/api/students/{student.id}/")
        self.assertEqual(response.status_code, 202)

        student.refresh_from_db()
        self.assertEqual(student.status, "Inactive")
        self.assertNotEqual(student.email, "alice@example.com")
        self.assertIn("@", student.email)

class TeacherViewSetTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(username="admin", password="adminpass", email="admin@example.com")
        self.client.force_authenticate(user=self.admin_user)

        self.teacher_user = User.objects.create_user(username="teacher1", password="pass123")
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            first_name="Test",
            last_name="Teacher",
            email="teacher@example.com",
            phone=1234567890,
            subject="Math",
            e_id="T001",
            doj=date.today(),
            status="Active"
        )

    def test_teacher_create_success(self):
        payload = {
            "first_name": "John",
            "last_name": "Doe",
            "username": "john_teacher",
            "password": "securepass123",
            "email": "john@example.com",
            "phone": "9876543210",
            "subject": "Science",
            "e_id": "T002",
            "doj": "2025-09-30",
            "status": "Active"
        }
        response = self.client.post("/api/teachers/", payload, format='json')
        self.assertEqual(response.status_code, 201)
        teacher = Teacher.objects.get(email="john@example.com")
        self.assertEqual(teacher.first_name, "John")
        self.assertEqual(teacher.e_id, "T002")

    def test_teacher_create_duplicate_username(self):
        payload = {
            "first_name": "Duplicate",
            "last_name": "User",
            "username": "teacher1",  
            "password": "pass123",
            "email": "newemail@example.com",
            "phone": "1231231234",
            "subject": "Math",
            "e_id": "T003",
            "doj": "2025-09-30",
            "status": "Active"
        }
        response = self.client.post("/api/teachers/", payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.data)

    def test_teacher_create_duplicate_email(self):
        User.objects.create_user(username="existinguser", password="pass123", email="duplicate@example.com")
        
        payload = {
            "first_name": "Duplicate",
            "last_name": "Email",
            "username": "newusername",
            "password": "pass123",
            "email": "duplicate@example.com", 
            "phone": "1231231234",
            "subject": "Math",
            "e_id": "T004",
            "doj": "2025-09-30",
            "status": "Active"
        }

        response = self.client.post("/api/teachers/", payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_teacher_create_duplicate_eid(self):
        payload = {
            "first_name": "Duplicate",
            "last_name": "EID",
            "username": "uniqueusername",
            "password": "pass123",
            "email": "unique@example.com",
            "phone": "1231231234",
            "subject": "Math",
            "e_id": "T001", 
            "doj": "2025-09-30",
            "status": "Active"
        }
        response = self.client.post("/api/teachers/", payload, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn("e_id", response.data)

    def test_teacher_list(self):
        response = self.client.get("/api/teachers/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data), 1)

    def test_teacher_retrieve(self):
        response = self.client.get(f"/api/teachers/{self.teacher.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["first_name"], self.teacher.first_name)

    def test_teacher_update(self):
        payload = {"first_name": "UpdatedName", "subject": "Physics"}
        response = self.client.patch(f"/api/teachers/{self.teacher.id}/", payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.first_name, "UpdatedName")
        self.assertEqual(self.teacher.subject, "Physics")

    def test_me_endpoint_teacher(self):
        self.client.force_authenticate(user=self.teacher_user)
        response = self.client.get("/api/teachers/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], self.teacher.email)

    def test_me_endpoint_non_teacher(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/teachers/me/")
        self.assertEqual(response.status_code, 403) 

    def test_me_endpoint_teacher_no_profile(self):
        user = User.objects.create_user(username="noprof", password="pass")
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/teachers/me/")
        self.assertEqual(response.status_code, 404) 

class PaymentGRPCClientTestCase(TestCase):
    @patch("users.payment_client.payment_pb2_grpc.PaymentServiceStub")
    @patch("users.payment_client.grpc.insecure_channel")
    def setUp(self, mock_channel, mock_stub_class):
        self.mock_stub = MagicMock()
        mock_stub_class.return_value = self.mock_stub
        self.client = PaymentGRPCClient(host="127.0.0.1", port=50052)

        teacher_user = User.objects.create_user(username="teacher1", password="pass")
        self.teacher = Teacher.objects.create(
            user=teacher_user,
            first_name="Test",
            last_name="Teacher",
            email="teacher@example.com",
            phone=1234567890,
            subject="Math",
            e_id="T001",
            doj=date.today(),
            status="Active"
        )

    def test_get_token_adds_teacher_student_id_and_role(self):
        user = User.objects.create_user(username="studuser", password="pass")
        student = Student.objects.create(
            user=user, first_name="S", last_name="U", email="suser@example.com",
            phone_number="1234567890", roll_number="R999", grade=5,
            academic_year="2025-2026", date_of_birth="2010-01-01",
            admission_date="2020-06-01", status="Active", assigned_teacher=self.teacher
        )

        token = CustomTokenObtainPairSerializer.get_token(user)
        self.assertEqual(token['role'], 'student')
        self.assertEqual(token['student_id'], student.id)

    def test_allocate_fee_calls_stub(self):
        self.client.allocate_fee(
            grade=5,
            academic_year="2025-2026",
            base_fee=1000.0,
            due_date="2025-12-01",
            fine_per_day=10.0
        )
        self.mock_stub.AllocateFee.assert_called_once()

    def test_allocate_fee_for_student_calls_stub(self):
        self.client.allocate_fee_for_student(student_id=1, grade=5, academic_year="2025-2026")
        self.mock_stub.AllocateFeeForStudent.assert_called_once()

    def test_initiate_payment_calls_stub(self):
        self.client.initiate_payment(student_fee_id=1, student_id=1, gateway="razorpay")
        self.mock_stub.InitiatePayment.assert_called_once()

    def test_simulate_razorpay_payment_calls_stub(self):
        self.client.simulate_razorpay_payment(payment_id=1, razorpay_order_id="order123")
        self.mock_stub.SimulateRazorpayPayment.assert_called_once()

    def test_verify_payment_calls_stub(self):
        self.client.verify_payment(
            payment_id=1,
            razorpay_order_id="order123",
            razorpay_payment_id="pay123",
            razorpay_signature="sig123"
        )
        self.mock_stub.VerifyRazorpayPayment.assert_called_once()

    def test_generate_receipt_calls_stub(self):
        student = MagicMock(id=1, first_name="John", last_name="Doe", roll_number="R001", grade=5, academic_year="2025-2026")
        self.client.generate_receipt(payment_id=1, student=student)
        self.mock_stub.GenerateReceipt.assert_called_once()

    def test_list_logs_calls_stub(self):
        self.client.list_logs()
        self.mock_stub.ListTransactionLogs.assert_called_once()

class ImportStudentsCSVTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            username="admin", password="adminpass", email="admin@example.com"
        )
        self.client.force_authenticate(user=self.admin_user)

        # Teacher
        self.teacher = Teacher.objects.create(
            user=User.objects.create_user(username="teacher1", password="pass123", email="teacher@example.com"),
            first_name="Test",
            last_name="Teacher",
            email="teacher@example.com",
            phone=1234567890,
            subject="Math",
            e_id="T001",
            doj=date.today(),
            status="Active"
        )

    def generate_csv_file(self, rows):
        """Helper: create a CSV file from a list of dicts."""
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=[
            "username", "password", "email", "first_name", "last_name",
            "phone_number", "roll_number", "grade", "academic_year",
            "date_of_birth", "admission_date", "status", "assigned_teacher_id"
        ])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return SimpleUploadedFile("students.csv", output.getvalue().encode("utf-8"), content_type="text/csv")

    def test_import_students_success(self):
        """Test successful CSV import with valid data"""
        rows = [{
            "username": "student1",
            "password": "pass123",
            "email": "student1@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "phone_number": "1234567890",
            "roll_number": "R001",
            "grade": "5",
            "academic_year": "2025-2026",
            "date_of_birth": "2010-01-01",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher_id": str(self.teacher.id),
        }]
        file = self.generate_csv_file(rows)

        response = self.client.post(
            "/api/import/students/",
            {"file": file},
            format="multipart"
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("1 students imported successfully", response.data["message"])
        self.assertEqual(Student.objects.count(), 1)

    def test_import_students_invalid_file_format(self):
        """Test uploading non-CSV file"""
        file = SimpleUploadedFile("students.txt", b"invalid data", content_type="text/plain")
        response = self.client.post(
            "/api/import/students/",
            {"file": file},
            format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Invalid file format", response.data["error"])

    def test_import_students_duplicate_roll_number(self):
        """Test duplicate roll number handling"""
        Student.objects.create(
            user=User.objects.create_user(username="dup", password="pass", email="dup@example.com"),
            first_name="Dup",
            last_name="User",
            email="dup@example.com",
            phone_number="9999999999",
            roll_number="R002",
            grade=6,
            academic_year="2025-2026",
            date_of_birth="2010-02-02",
            admission_date="2020-06-01",
            status="Active",
            assigned_teacher=self.teacher,
        )

        rows = [{
            "username": "student2",
            "password": "pass123",
            "email": "student2@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "phone_number": "1234567890",
            "roll_number": "R002",  
            "grade": "6",
            "academic_year": "2025-2026",
            "date_of_birth": "2010-03-03",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher_id": str(self.teacher.id),
        }]
        file = self.generate_csv_file(rows)

        response = self.client.post(
            "/api/import/students/",
            {"file": file},
            format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Roll number R002 already exists", str(response.data["errors"]))

    def test_import_students_invalid_teacher_id(self):
        """Test invalid teacher assignment"""
        rows = [{
            "username": "student3",
            "password": "pass123",
            "email": "student3@example.com",
            "first_name": "Jack",
            "last_name": "Smith",
            "phone_number": "1234567890",
            "roll_number": "R003",
            "grade": "7",
            "academic_year": "2025-2026",
            "date_of_birth": "2010-04-04",
            "admission_date": "2020-06-01",
            "status": "Active",
            "assigned_teacher_id": "9999",  
        }]
        file = self.generate_csv_file(rows)

        response = self.client.post(
            "/api/import/students/",
            {"file": file},
            format="multipart"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Teacher with ID 9999 not found", str(response.data["errors"]))
