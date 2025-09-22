import grpc
from concurrent import futures
import time
import os
import django
import hmac, hashlib
# setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "payment_service.settings")
django.setup()
from django.conf import settings
from payments.models import FeeStructure, StudentFee , Fine
import payment_pb2,payment_pb2_grpc
from payment_pb2 import FeeAllocationResponse,FeeAllocationRequest , AllocateFeeForStudentResponse
from payment_pb2_grpc import PaymentServiceServicer
from django.utils import timezone
from django.db import transaction
import razorpay
from payment_pb2 import InitiatePaymentRequest, InitiatePaymentResponse
from payments.models import Payment,TransactionLog
from reportlab.pdfgen import canvas
from payments.models import Receipt
from datetime import datetime
from payments.validators import validate_fee_structure_data,validate_student_fee,validate_payment
from django.db import IntegrityError, DatabaseError, OperationalError 
from django.core.exceptions import ValidationError

class PaymentService(payment_pb2_grpc.PaymentServiceServicer):
    def AllocateFee(self, request, context):
        try:
            grade = request.grade
            academic_year = request.academic_year
            base_fee = request.base_fee
            fine_per_day = request.fine_per_day

            # Convert due_date string to date if needed
            if isinstance(request.due_date, str):
                due_date = datetime.strptime(request.due_date, "%Y-%m-%d").date()
            else:
                due_date = request.due_date

            # Now safe to use in ORM and comparisons
            validate_fee_structure_data(grade, academic_year, base_fee, due_date, fine_per_day)

            fee_structure, created = FeeStructure.objects.get_or_create(
                grade=grade,
                academic_year=academic_year,
                defaults={
                    "base_fee": base_fee,
                    "due_date": due_date,
                    "fine_per_day": fine_per_day,
                }
            )

            if not created:
                fee_structure.base_fee = base_fee
                fee_structure.due_date = due_date
                fee_structure.fine_per_day = fine_per_day
                fee_structure.save()

            TransactionLog.objects.create(
                log_message=f"FeeStructure created/updated for grade {grade}",
                log_type="info"
            )

            return payment_pb2.FeeAllocationResponse(
                message=f"Fee allocated successfully for grade {grade}, year {academic_year}"
            )

        except Exception as e:
            TransactionLog.objects.create(
                log_message=f"Fee allocation failed: {str(e)}",
                log_type="error"
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return payment_pb2.FeeAllocationResponse(message="Fee allocation failed")
        
    def AllocateFeeForStudent(self, request, context):
        try:
            fee_structure = FeeStructure.objects.get(
                grade=int(request.grade),
                academic_year=request.academic_year
            )
            try:
                validate_student_fee(request.student_id, fee_structure)
            except ValidationError as ve:
                TransactionLog.objects.create(
                    log_message=f"Fee allocation failed validation for student {request.student_id}: {str(ve)}",
                    log_type="error"
                )
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details(str(ve))
                return AllocateFeeForStudentResponse(message=str(ve))

            student_fee = StudentFee.objects.create(
                student_id=request.student_id,  
                fee_structure=fee_structure,
                due_date=fee_structure.due_date,
                total_amount=fee_structure.base_fee
            )

            # check overdue
            today = timezone.now().date()
            fine_amount = 0
            if today > fee_structure.due_date:
                days_overdue = (today - fee_structure.due_date).days
                fine_amount = days_overdue * fee_structure.fine_per_day
                Fine.objects.create(
                    student_fee=student_fee,
                    student_id=request.student_id,
                    days_overdue=days_overdue,
                    fine_amount=fine_amount,
                    calculated_on=today
                )

            student_fee.total_amount = fee_structure.base_fee + fine_amount
            student_fee.save()
            TransactionLog.objects.create(
                log_message=f"Fee allocated for student {request.student_id}",      
                log_type="info"
            )
            return AllocateFeeForStudentResponse(
                message=f"Fee allocated for student {request.student_id}"
            )
        except FeeStructure.DoesNotExist:
            TransactionLog.objects.create(
                log_message=f"Fee structure not found for grade={request.grade}, year={request.academic_year}",
                log_type="error"
            )
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("No FeeStructure for grade/year")
            return AllocateFeeForStudentResponse(message="Fee structure not found")
        except Exception as e:
            TransactionLog.objects.create(
                log_message=f"Unexpected error during fee allocation for student {request.student_id}: {str(e)}",
                log_type="error"
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return AllocateFeeForStudentResponse(message="Fee allocation failed")

    def InitiatePayment(self, request, context):
        try:
            with transaction.atomic():
                student_fee = StudentFee.objects.select_for_update().get(
                    id=request.student_fee_id, student_id=request.student_id
                )
                
                if student_fee.lock == 1:
                    TransactionLog.objects.create(
                        log_message=f"Payment lock conflict for StudentFee {student_fee.id}",#f- fromatted string literal
                        log_type="warning"
                    )
                    context.set_code(grpc.StatusCode.ABORTED)#status code which returns when a transaction conflict or lock happens
                    context.set_details("Payment is already being processed")
                    return InitiatePaymentResponse(message="Payment already in process")

                student_fee.lock = 1
                student_fee.save()

                if student_fee.status == "paid":
                    TransactionLog.objects.create(
                        log_message=f"Fee already paid for StudentFee {student_fee.id}",
                        log_type="info"
                    )
                    student_fee.lock = 0
                    student_fee.save()
                    return InitiatePaymentResponse(message="Fee already paid")

                today = timezone.now().date()
                fine_amount = 0
                if today > student_fee.due_date:
                    days_overdue = (today - student_fee.due_date).days
                    fine_amount = days_overdue * student_fee.fee_structure.fine_per_day

                    Fine.objects.update_or_create(
                        student_fee=student_fee,
                        student_id=request.student_id,
                        defaults={
                            "days_overdue": days_overdue,
                            "fine_amount": fine_amount,
                            "calculated_on": today,
                        },
                    )
                    TransactionLog.objects.create(
                        log_message=f"Fine calculated: {fine_amount} for StudentFee {student_fee.id}",
                        log_type="info"
                    )
                student_fee.total_amount = student_fee.fee_structure.base_fee + fine_amount
                student_fee.save()

                existing_payment = Payment.objects.filter(
                    student_fee=student_fee, status="initiated"
                ).first()
                if existing_payment:
                    return InitiatePaymentResponse(message="Payment already initiated")
                if request.gateway == "razorpay":
                    client = razorpay.Client(
                        auth=(os.getenv("RAZORPAY_KEY_ID"), os.getenv("RAZORPAY_KEY_SECRET"))
                    )
                    order = client.order.create(
                        {
                            "amount": int(student_fee.total_amount * 100),
                            "currency": "INR",
                            "receipt": f"{student_fee.id}",
                            "payment_capture": 1,
                        }
                    )
                    payment = Payment.objects.create(
                        student_fee=student_fee,
                        gateway="razorpay",
                        transaction_id=order["id"],
                        amount=student_fee.total_amount,
                        status="initiated",
                    )
                    TransactionLog.objects.create(
                        log_message=f"Razorpay order {order['id']} created",
                        log_type="info",
                    )
                    return InitiatePaymentResponse(
                        message="Razorpay order created",
                        payment_id=payment.id,
                        order_id=order["id"],
                        amount=float(student_fee.total_amount),
                        currency="INR",
                    )

                elif request.gateway == "offline":
                    payment = Payment.objects.create(
                        student_fee=student_fee,
                        gateway="offline",
                        amount=student_fee.total_amount,
                        status="success",
                        remarks="Cash/Offline",
                    )
                    student_fee.paid_amount = student_fee.total_amount
                    student_fee.status = "paid"
                    student_fee.save()
                    try:
                        TransactionLog.objects.create(
                            log_message="Offline payment recorded",
                            log_type="info",
                        )
                    except Exception as e:
                        print("TransactionLog creation failed:", str(e))
                    return InitiatePaymentResponse(
                        message="Offline payment successful",
                        payment_id=payment.id,
                        order_id="",
                        amount=float(student_fee.total_amount),
                        currency="INR",
                    )

                else:
                    TransactionLog.objects.create(
                        log_message=f"Unsupported gateway: {request.gateway} for StudentFee {student_fee.id}",
                        log_type="error"
                    )
                    context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                    context.set_details("Unsupported gateway")
                    return InitiatePaymentResponse(message="Unsupported gateway")

        except StudentFee.DoesNotExist:
            TransactionLog.objects.create(
                log_message=f"Student fee not found",
                log_type="error"
            )
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("StudentFee not found")
            return InitiatePaymentResponse(message="StudentFee not found")
        except Exception as e:
            TransactionLog.objects.create(
                log_message=f"Payment initiation failed: {str(e)}",
                log_type="error"
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return InitiatePaymentResponse(message="Payment initiation failed")

    def SimulateRazorpayPayment(self, request, context):
        try:
            payment = Payment.objects.get(
                id=request.payment_id,
                transaction_id=request.razorpay_order_id
            )
        except Payment.DoesNotExist:
            TransactionLog.objects.create(
                log_message=f"Simulate payment failed: Payment record not found (payment_id={request.payment_id}, order_id={request.razorpay_order_id})",
                log_type="error"
            )
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Payment record not found")
            return payment_pb2.SimulateRazorpayResponse()

        try:
            razorpay_payment_id = str(request.payment_id) 
            razorpay_order_id = request.razorpay_order_id
            # generate signature
            msg = f"{razorpay_order_id}|{razorpay_payment_id}"
            generated_signature = hmac.new(
                bytes(settings.RAZORPAY_KEY_SECRET, "utf-8"),
                bytes(msg, "utf-8"),
                hashlib.sha256
            ).hexdigest()
        except Exception as e:
            TransactionLog.objects.create(
                log_message=f"Signature generation failed: {str(e)}",
                log_type="error"
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to generate signature: {str(e)}")
            return payment_pb2.SimulateRazorpayResponse()

        TransactionLog.objects.create(
            log_message=f"Simulated Razorpay payment generated. razorpay_payment_id={razorpay_payment_id}",
            log_type="info"
        )

        return payment_pb2.SimulateRazorpayResponse(
            payment_id=payment.id,
            razorpay_order_id=request.razorpay_order_id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_signature=generated_signature
        )
    
    def VerifyRazorpayPayment(self, request, context):
        try:
            payment_id = request.payment_id
            razorpay_order_id = request.razorpay_order_id
            razorpay_payment_id = request.razorpay_payment_id
            razorpay_signature = request.razorpay_signature

            if not all([payment_id, razorpay_order_id, razorpay_payment_id, razorpay_signature]):
                context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
                context.set_details("Missing required payment fields")
                return payment_pb2.VerifyRazorpayResponse()

            try:
                payment = Payment.objects.get(id=payment_id)
            except Payment.DoesNotExist:
                TransactionLog.objects.create(
                    log_message=f"Payment record not found for payment_id={payment_id}",
                    log_type="error"
                )
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Payment record not found")
                return payment_pb2.VerifyRazorpayResponse()

            # Verify signature
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            try:
                client.utility.verify_payment_signature({
                    "razorpay_order_id": razorpay_order_id,
                    "razorpay_payment_id": razorpay_payment_id,
                    "razorpay_signature": razorpay_signature
                })
            except razorpay.errors.SignatureVerificationError:
                TransactionLog.objects.create(
                    log_message="Razorpay signature verification failed",
                    log_type="error"
                )
                context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                context.set_details("Payment verification failed")
                return payment_pb2.VerifyRazorpayResponse()

            with transaction.atomic():
                # Update payment and student fee
                payment.status = "success"
                payment.transaction_id = razorpay_payment_id
                payment.save()

                student_fee = payment.student_fee
                student_fee.paid_amount = student_fee.total_amount
                student_fee.status = "paid"
                student_fee.lock = 0
                student_fee.save()

                TransactionLog.objects.create(
                    log_message=f"Payment verified successfully. Razorpay Payment ID: {razorpay_payment_id}",
                    log_type="success"
                )

                return payment_pb2.VerifyRazorpayResponse(
                    message="Payment verified successfully",
                    receipt_url=""
                )
        #db error , invalid input error , server connection error,gateway error
        except Exception as e:
            TransactionLog.objects.create(
                log_message=f"Unexpected error in VerifyRazorpayPayment: {str(e)}",
                log_type="error"
            )
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return payment_pb2.VerifyRazorpayResponse()

    def GenerateReceipt(self, request, context):
        try:
            try:
                payment = Payment.objects.get(id=request.payment_id)
            except Payment.DoesNotExist:
                TransactionLog.objects.create(
                    log_message=f"Payment record not found for payment_id={request.payment_id}",
                    log_type="error"
                )
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Payment record not found")
                return payment_pb2.GenerateReceiptResponse()
            

            student_name = request.student_name
            roll_number = request.roll_number
            grade = request.grade
            academic_year = request.academic_year

            try:
            # Generate PDF receipt
                receipt_folder = os.path.join(settings.MEDIA_ROOT, 'receipts')
                os.makedirs(receipt_folder, exist_ok=True)
                filename = f"RCPT_{payment.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
                file_path = os.path.join(receipt_folder, filename)
                receipt_path = f"receipts/{filename}"

                c = canvas.Canvas(file_path)
                c.setFont("Helvetica-Bold", 16)
                c.drawString(200, 800, "Fee Payment Receipt")
                c.setFont("Helvetica", 12)
                c.drawString(50, 750, f"Student Name: {student_name}")
                c.drawString(50, 730, f"Roll Number: {roll_number}")
                c.drawString(50, 710, f"Class/Grade: {grade}")
                c.drawString(50, 690, f"Academic Year: {academic_year}")
                c.drawString(50, 670, f"Total Fee Paid: ₹{payment.amount}")
                c.drawString(50, 650, f"Payment Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                c.drawString(50, 630, f"Payment Method: {payment.gateway}")
                c.drawString(50, 610, f"Transaction ID: {payment.transaction_id}")
                c.showPage()
                c.save()

                TransactionLog.objects.create(
                    log_message=f"Receipt PDF generated at {file_path}",
                    log_type="info"
                )
            except Exception as e:
                TransactionLog.objects.create(
                    log_message=f"Receipt PDF generation failed: {str(e)}",
                    log_type="error"
                )
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"PDF generation failed: {str(e)}")
                return payment_pb2.GenerateReceiptResponse()

            try:
                receipt = Receipt.objects.create(
                    payment=payment,
                    receipt_number=f"RCPT{payment.id}",
                    student_id=request.student_id,  # from user_service
                    fee_structure=payment.student_fee.fee_structure,
                    amount_paid=payment.amount,
                    fine_amount=0,
                    total_amount=payment.amount,
                    receipt_file=receipt_path,
                    issued_date=timezone.now()
                )

                receipt_url = settings.MEDIA_URL + receipt.receipt_file

                TransactionLog.objects.create(
                    log_message=f"Receipt record created successfully, receipt_id={receipt.id}, url={receipt_url}",
                    log_type="success"
                )

                return payment_pb2.GenerateReceiptResponse(
                    message="Receipt generated successfully",
                    receipt_url=receipt_url
                )
            except Exception as e:
                TransactionLog.objects.create(
                    log_message=f"Receipt DB entry creation failed: {str(e)}",
                    log_type="error"
                )
                context.set_code(grpc.StatusCode.INTERNAL)
                context.set_details(f"Receipt save failed: {str(e)}")
            return payment_pb2.GenerateReceiptResponse()

        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return payment_pb2.GenerateReceiptResponse()

    def ListTransactionLogs(self, request, context):
        logs = TransactionLog.objects.all().order_by('-created_at')
        response = payment_pb2.ListTransactionLogsResponse()

        for log in logs:
            response.logs.add(
                id=log.id,
                log_message=log.log_message,
                log_type=log.log_type,
                created_at=str(log.created_at)
            )
        return response
            
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    payment_pb2_grpc.add_PaymentServiceServicer_to_server(PaymentService(), server)
    server.add_insecure_port("[::]:50052")  # listen on port 50052
    server.start()
    print("Payment gRPC server started on port 50052")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()


from payments.payment_client import PaymentGRPCClient

