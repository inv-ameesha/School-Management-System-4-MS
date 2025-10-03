import os
import unittest
from django.test import TestCase
from django.urls import reverse
import grpc
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from datetime import date, datetime
from .payment_client import PaymentGRPCClient
from .user_client import UserGRPCClient
from .grpc_server import PaymentService
from payment_pb2 import (
    FeeAllocationRequest,
    FeeAllocationResponse,
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    SimulateRazorpayRequest,
    SimulateRazorpayResponse,
    VerifyRazorpayRequest,
    VerifyRazorpayResponse,
    GenerateReceiptRequest,
    GenerateReceiptResponse
)

class FeePaymentTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass"
        )
        self.admin_user.role = "admin"

        self.student_user = User.objects.create_user(
            username="student1", email="student1@example.com", password="studentpass"
        )
        self.student_user.student = MagicMock()
        self.student_user.student.id = 1
        self.student_user.role = "student"

        self.client = APIClient()

    @patch("payments.views.UserGRPCClient")
    @patch("payments.views.PaymentGRPCClient")
    def test_fee_allocation_success(self, mock_payment_client, mock_user_client):
        self.client.force_authenticate(user=self.admin_user)

        mock_user_instance = mock_user_client.return_value
        mock_user_instance.get_students_by_grade_year.return_value = [1, 2, 3]
        mock_user_instance.close.return_value = None

        mock_payment_instance = mock_payment_client.return_value
        mock_payment_instance.allocate_fee.return_value = MagicMock(message="Fee allocated successfully")
        mock_payment_instance.close.return_value = None

        data = {
            "grade": 5,
            "academic_year": "2025-2026",
            "base_fee": 1000,
            "due_date": "2025-10-15",
            "fine_per_day": 50
        }

        url = reverse("fee-allocation")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Fee allocated successfully")

    @patch("payments.views.PaymentGRPCClient")
    def test_initiate_payment_success(self, mock_payment_client):
        self.client.force_authenticate(user=self.student_user)

        mock_payment_instance = mock_payment_client.return_value
        mock_payment_instance.initiate_payment.return_value = MagicMock(
            message="Payment initiated",
            payment_id=101,
            order_id="ORD123",
            amount=1000,
            currency="INR"
        )
        mock_payment_instance.close.return_value = None

        data = {"student_fee_id": 1, "gateway": "razorpay"}
        url = reverse("initiate-payment")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Payment initiated")
        self.assertEqual(response.data["payment_id"], 101)

    @patch("payments.views.PaymentGRPCClient")
    def test_simulate_razorpay_payment_success(self, mock_payment_client):
        self.client.force_authenticate(user=self.student_user)

        mock_payment_instance = mock_payment_client.return_value
        mock_payment_instance.simulate_razorpay_payment.return_value = MagicMock(
            payment_id=101,
            razorpay_order_id="ORD123",
            razorpay_payment_id="PAY123",
            razorpay_signature="SIGN123"
        )
        mock_payment_instance.close.return_value = None

        data = {"payment_id": 101, "razorpay_order_id": "ORD123"}
        url = reverse("simulate-payment")
        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["razorpay_payment_id"], "PAY123")

    @patch("payments.views.PaymentGRPCClient")
    def test_verify_razorpay_payment_success(self, mock_payment_client):
        self.client.force_authenticate(user=self.student_user)

        mock_payment_instance = mock_payment_client.return_value
        mock_payment_instance.verify_payment.return_value = MagicMock(message="Payment verified successfully")
        mock_payment_instance.generate_receipt.return_value = MagicMock(
            message="Receipt generated",
            receipt_url="http://example.com/receipt.pdf"
        )

        data = {
            "payment_id": 101,
            "razorpay_order_id": "ORD123",
            "razorpay_payment_id": "PAY123",
            "razorpay_signature": "SIGN123"
        }

        url = reverse("verify-payment")
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Receipt generated")
        self.assertEqual(response.data["receipt_url"], "http://example.com/receipt.pdf")

class UserGRPCClientTestCase(unittest.TestCase):
    @patch("payments.user_client.user_service_pb2_grpc.UserServiceStub")
    @patch("grpc.insecure_channel")
    def setUp(self, mock_channel, mock_stub_class):
        self.mock_channel = mock_channel.return_value
        self.mock_stub = mock_stub_class.return_value
        self.client = UserGRPCClient(host="127.0.0.1", port=50053)

    def test_get_students_by_grade_year(self):
        mock_response = MagicMock()
        mock_response.students = ["student1", "student2"]
        self.mock_stub.GetStudentsByGradeYear.return_value = mock_response

        students = self.client.get_students_by_grade_year(grade=5, academic_year="2025-2026")
        self.assertEqual(students, ["student1", "student2"])
        self.mock_stub.GetStudentsByGradeYear.assert_called_once()

    def test_get_teacher_by_user_success(self):
        mock_response = MagicMock()
        mock_response.teacher_id = 10
        self.mock_stub.GetTeacherByUserId.return_value = mock_response

        teacher = self.client.get_teacher_by_user(user_id=1)
        self.assertEqual(teacher.teacher_id, 10)
        self.mock_stub.GetTeacherByUserId.assert_called_once()

    def test_get_teacher_by_user_rpc_error(self):
        self.mock_stub.GetTeacherByUserId.side_effect = grpc.RpcError("Service unavailable")
        with self.assertRaises(grpc.RpcError):
            self.client.get_teacher_by_user(user_id=1)

    def test_get_student_by_user(self):
        mock_response = MagicMock()
        mock_response.student_id = 5
        self.mock_stub.GetStudentByUserId.return_value = mock_response

        student = self.client.get_student_by_user(user_id=1)
        self.assertEqual(student.student_id, 5)
        self.mock_stub.GetStudentByUserId.assert_called_once()

    def test_get_student_by_id(self):
        mock_response = MagicMock()
        mock_response.student_id = 20
        self.mock_stub.GetStudentById.return_value = mock_response

        student = self.client.get_student_by_id(student_id=20)
        self.assertEqual(student.student_id, 20)
        self.mock_stub.GetStudentById.assert_called_once()

    def test_close(self):
        self.client.close()
        self.mock_channel.close.assert_called_once()

class PaymentGRPCClientTestCase(unittest.TestCase):
    @patch("payments.payment_client.payment_pb2_grpc.PaymentServiceStub")
    @patch("grpc.insecure_channel")
    def setUp(self, mock_channel, mock_stub_class):
        self.mock_channel = mock_channel.return_value
        self.mock_stub = mock_stub_class.return_value
        self.client = PaymentGRPCClient(host="127.0.0.1", port=50052)

    def test_allocate_fee(self):
        mock_response = MagicMock()
        mock_response.message = "Fee allocated"
        self.mock_stub.AllocateFee.return_value = mock_response

        response = self.client.allocate_fee(5, "2025-2026", 1000.0, date(2025,12,1), 10.0)
        self.assertEqual(response.message, "Fee allocated")
        self.mock_stub.AllocateFee.assert_called_once()

    def test_initiate_payment(self):
        mock_response = MagicMock()
        mock_response.payment_id = 1
        mock_response.message = "Payment initiated"
        self.mock_stub.InitiatePayment.return_value = mock_response

        response = self.client.initiate_payment(student_fee_id=1, student_id=2, gateway="razorpay")
        self.assertEqual(response.payment_id, 1)
        self.mock_stub.InitiatePayment.assert_called_once()

    def test_simulate_razorpay_payment(self):
        mock_response = MagicMock()
        mock_response.payment_id = 1
        mock_response.razorpay_order_id = "order_123"
        mock_response.razorpay_payment_id = "pay_123"
        mock_response.razorpay_signature = "sig_123"
        self.mock_stub.SimulateRazorpayPayment.return_value = mock_response

        response = self.client.simulate_razorpay_payment(payment_id=1, razorpay_order_id="order_123")
        self.assertEqual(response.razorpay_order_id, "order_123")
        self.mock_stub.SimulateRazorpayPayment.assert_called_once()

    def test_verify_payment(self):
        mock_response = MagicMock()
        mock_response.message = "Payment verified successfully"
        self.mock_stub.VerifyRazorpayPayment.return_value = mock_response

        response = self.client.verify_payment(1, "order_123", "pay_123", "sig_123")
        self.assertEqual(response.message, "Payment verified successfully")
        self.mock_stub.VerifyRazorpayPayment.assert_called_once()

    def test_generate_receipt(self):
        mock_response = MagicMock()
        mock_response.message = "Receipt generated"
        mock_response.receipt_url = "http://example.com/receipt.pdf"
        self.mock_stub.GenerateReceipt.return_value = mock_response

        response = self.client.generate_receipt(payment_id=1, student_id=2)
        self.assertEqual(response.receipt_url, "http://example.com/receipt.pdf")
        self.mock_stub.GenerateReceipt.assert_called_once()

    def test_close_channel(self):
        self.client.close()
        self.mock_channel.close.assert_called_once()

class PaymentServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.service = PaymentService()
        self.mock_context = MagicMock()

    @patch("payments.grpc_server.FeeStructure.objects.get_or_create")
    @patch("payments.grpc_server.TransactionLog.objects.create")
    def test_allocate_fee_success(self, mock_log, mock_get_or_create):
        mock_get_or_create.return_value = (MagicMock(), True)
        request = FeeAllocationRequest(
            grade=5, academic_year="2025-2026", base_fee=1000, due_date="2025-10-15", fine_per_day=50
        )
        response = self.service.AllocateFee(request, self.mock_context)
        self.assertIsInstance(response, FeeAllocationResponse)
        self.assertIn("Fee allocated successfully", response.message)

    @patch("payments.grpc_server.razorpay.Client")
    @patch("payments.grpc_server.Payment.objects.create")
    @patch("payments.grpc_server.TransactionLog.objects.create")
    @patch("payments.grpc_server.StudentFee.objects.select_for_update")
    def test_initiate_payment_razorpay(self, mock_select, mock_log, mock_payment_create, mock_razorpay_client):
        mock_student_fee = MagicMock()
        mock_student_fee.id = 1
        mock_student_fee.student_id = 1
        mock_student_fee.lock = 0
        mock_student_fee.status = "pending"
        mock_student_fee.due_date = datetime.today().date()
        mock_student_fee.fee_structure = MagicMock(base_fee=1000, fine_per_day=50)
        mock_student_fee.save = MagicMock()
        mock_select.return_value.get.return_value = mock_student_fee

        mock_order = {"id": "order_123"}
        mock_razorpay_client.return_value.order.create.return_value = mock_order

        mock_payment_create.return_value = MagicMock(id=1)

        request = InitiatePaymentRequest(student_fee_id=1, student_id=1, gateway="razorpay")
        service = PaymentService()
        response = service.InitiatePayment(request, MagicMock())

        self.assertIsInstance(response, InitiatePaymentResponse)

    @patch("payments.grpc_server.Payment.objects.get")
    @patch("payments.grpc_server.TransactionLog.objects.create")
    @patch("payments.grpc_server.settings")
    def test_simulate_razorpay_payment_success(self, mock_settings, mock_log, mock_payment_get):
        mock_payment = MagicMock()
        mock_payment.id = 101
        mock_payment_get.return_value = mock_payment
        mock_settings.RAZORPAY_KEY_SECRET = "secret"

        request = SimulateRazorpayRequest(payment_id=101, razorpay_order_id="order_123")
        response = self.service.SimulateRazorpayPayment(request, self.mock_context)
        self.assertIsInstance(response, SimulateRazorpayResponse)
        self.assertEqual(response.payment_id, 101)
        self.assertEqual(response.razorpay_order_id, "order_123")

    @patch("payments.grpc_server.Payment.objects.get")
    @patch("payments.grpc_server.TransactionLog.objects.create")
    @patch("payments.grpc_server.razorpay.Client")
    def test_verify_razorpay_payment_success(self, mock_razorpay, mock_log, mock_payment_get):
        mock_payment = MagicMock()
        mock_payment.student_fee = MagicMock()
        mock_payment_get.return_value = mock_payment

        request = VerifyRazorpayRequest(
            payment_id=1,
            razorpay_order_id="order_123",
            razorpay_payment_id="pay_123",
            razorpay_signature="sig_123"
        )
        response = self.service.VerifyRazorpayPayment(request, self.mock_context)
        self.assertIsInstance(response, VerifyRazorpayResponse)

    @patch("payments.grpc_server.Payment.objects.get")
    @patch("payments.grpc_server.UserGRPCClient")
    @patch("payments.grpc_server.Receipt.objects.create")
    @patch("payments.grpc_server.TransactionLog.objects.create")
    @patch("payments.grpc_server.os.makedirs")
    @patch("payments.grpc_server.canvas.Canvas")
    def test_generate_receipt_success(
            self, mock_canvas, mock_makedirs, mock_log,
            mock_receipt_create, mock_user_client, mock_payment_get):

        mock_payment = MagicMock()
        mock_payment.id = 101
        mock_payment.amount = 1000
        mock_payment.gateway = "razorpay"
        mock_payment.transaction_id = "txn_123"
        mock_payment.student_fee = MagicMock()
        mock_payment.student_fee.fee_structure = MagicMock()
        mock_payment_get.return_value = mock_payment

        mock_user_instance = mock_user_client.return_value
        mock_student_resp = MagicMock()
        mock_student_resp.found = True
        mock_student_resp.student.first_name = "John"
        mock_student_resp.student.last_name = "Doe"
        mock_student_resp.student.grade = 5
        mock_student_resp.student.academic_year = "2025-2026"
        mock_user_instance.get_student_by_id.return_value = mock_student_resp

        mock_receipt_create.return_value = MagicMock(id=1, receipt_file="receipts/fake.pdf")

        request = GenerateReceiptRequest(payment_id=101, student_id=1)
        service = PaymentService()
        response = service.GenerateReceipt(request, MagicMock())

        self.assertIsInstance(response, GenerateReceiptResponse)
        self.assertEqual(response.message, "Receipt generated successfully")
        self.assertTrue("receipts/" in response.receipt_url)

    @patch("payments.grpc_server.StudentFee.objects.select_for_update")
    @patch("payments.grpc_server.Payment.objects.create")
    @patch("payments.grpc_server.TransactionLog.objects.create")
    def test_initiate_offline_payment(self, mock_log, mock_payment_create, mock_select):
        student_fee = MagicMock()
        student_fee.id = 1
        student_fee.student_id = 1
        student_fee.lock = 0
        student_fee.status = "pending"
        student_fee.due_date = datetime.today().date()
        student_fee.fee_structure = MagicMock(base_fee=1000, fine_per_day=50)
        student_fee.save = MagicMock()   # <-- important
        student_fee.total_amount = 1000

        mock_select.return_value.get.return_value = student_fee
        mock_payment_create.return_value = MagicMock(id=2)

        request = InitiatePaymentRequest(student_fee_id=1, student_id=1, gateway="offline")
        response = self.service.InitiatePayment(request, self.mock_context)

if __name__ == "__main__":
    unittest.main()
