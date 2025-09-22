import grpc
import payment_pb2
from payment_pb2 import FeeAllocationRequest, FeeAllocationResponse , VerifyRazorpayRequest 
from payment_pb2 import VerifyRazorpayResponse
from payment_pb2 import InitiatePaymentRequest, InitiatePaymentResponse
from payment_pb2 import SimulateRazorpayRequest, SimulateRazorpayResponse
from payment_pb2 import AllocateFeeForStudentRequest, AllocateFeeForStudentResponse
from payment_pb2 import GenerateReceiptRequest, GenerateReceiptResponse
from payment_pb2 import StudentFeeRequest, StudentFeeListResponse, ListTransactionLogsRequest
import payment_pb2_grpc
from payment_pb2_grpc import PaymentServiceStub

class PaymentGRPCClient:
    def __init__(self, host="127.0.0.1", port=50052):  # payment_service running on 50052
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = payment_pb2_grpc.PaymentServiceStub(self.channel)

    def allocate_fee(self, grade, academic_year, base_fee, due_date, fine_per_day):
        request = payment_pb2.FeeAllocationRequest(
            grade=str(grade),
            academic_year=academic_year,
            base_fee=float(base_fee),
            due_date=due_date,
            fine_per_day=float(fine_per_day),
        )
        return self.stub.AllocateFee(request)
    
    def allocate_fee_for_student(self, student_id, grade, academic_year):
            request = payment_pb2.AllocateFeeForStudentRequest(
                student_id=student_id,
                grade=grade,
                academic_year=academic_year,
            )
            return self.stub.AllocateFeeForStudent(request)

    def initiate_payment(self, student_fee_id, student_id, gateway):
        request = payment_pb2.InitiatePaymentRequest(
            student_fee_id=student_fee_id,
            student_id=student_id,
            gateway=gateway,
        )
        return self.stub.InitiatePayment(request)

    def simulate_razorpay_payment(self, payment_id, razorpay_order_id):
        request = payment_pb2.SimulateRazorpayRequest(
            payment_id=payment_id,
            razorpay_order_id=razorpay_order_id
        )
        return self.stub.SimulateRazorpayPayment(request)

    def verify_payment(self, payment_id, razorpay_order_id, razorpay_payment_id, razorpay_signature):
        request = payment_pb2.VerifyRazorpayRequest(
            payment_id=payment_id,
            razorpay_order_id=razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=razorpay_signature
        )
        response = self.stub.VerifyRazorpayPayment(request)
        return response

    def generate_receipt(self, payment_id, student):
        request = payment_pb2.GenerateReceiptRequest(
            payment_id=int(payment_id),
            student_id=int(student.id),
            student_name=f"{student.first_name} {student.last_name}",
            roll_number=str(student.roll_number),  
            grade=str(student.grade),              
            academic_year=str(student.academic_year)  
        )
        return self.stub.GenerateReceipt(request)

    def list_logs(self):
        request = payment_pb2.ListTransactionLogsRequest()
        return self.stub.ListTransactionLogs(request)
