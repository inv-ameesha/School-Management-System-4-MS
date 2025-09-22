import grpc
import payment_pb2
import payment_pb2_grpc
from datetime import datetime
class PaymentGRPCClient:
    def __init__(self, host="127.0.0.1", port=50052):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = payment_pb2_grpc.PaymentServiceStub(self.channel)

    def allocate_fee(self, grade, academic_year, base_fee, due_date, fine_per_day):
        request = payment_pb2.FeeAllocationRequest(
            grade=grade,
            academic_year=academic_year,
            base_fee=base_fee,
            due_date=due_date.strftime("%Y-%m-%d"),
            fine_per_day=fine_per_day,
        )
        return self.stub.AllocateFee(request)
    
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
        return self.stub.VerifyRazorpayPayment(request)

    def generate_receipt(self, payment_id, student_id):
        request = payment_pb2.GenerateReceiptRequest(
            payment_id=payment_id,
            student_id=student_id,
        )
        return self.stub.GenerateReceipt(request)
    
    def close(self):        
        self.channel.close()
