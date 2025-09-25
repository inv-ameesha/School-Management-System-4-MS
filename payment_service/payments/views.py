from datetime import datetime
import traceback
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, permissions
import grpc
from .payment_client import PaymentGRPCClient
from .user_client import UserGRPCClient      
import logging
import traceback
from .serializers import (
    FeeAllocationSerializer,    
    InitiatePaymentSerializer,
    SimulateRazorpayPaymentSerializer,
)
from .permission import  IsStudent , IsAdminUser

logger = logging.getLogger(__name__)

class FeeAllocationView(APIView):
    permission_classes = [IsAdminUser]
    serializer_class = FeeAllocationSerializer
    def post(self, request):
        user = request.user
        data = request.data
        # pdb.set_trace()
        # Debug: log student info
        user_client = UserGRPCClient()
        try:
            students = user_client.get_students_by_grade_year(
                grade=data.get("grade"),
                academic_year=data.get("academic_year")
            )
            if not students:
                logger.info("No students found for this grade/year. Continuing fee allocation...")
        finally:
            user_client.close()
        # Debug: log types before gRPC
        try:
            grade_val = int(data.get("grade"))
            academic_year_val = str(data.get("academic_year"))
            base_fee_val = float(data.get("base_fee"))
            due_date_str = request.data.get("due_date")   
            due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            fine_val = float(data.get("fine_per_day"))

            client = PaymentGRPCClient()
            response = client.allocate_fee(
                grade=grade_val,
                academic_year=academic_year_val,
                base_fee=base_fee_val,
                due_date=due_date,
                fine_per_day=fine_val
            )
            logger.info("Payment service response: %s", response)
            return Response({"message": response.message}, status=status.HTTP_201_CREATED)

        except (ValueError, TypeError) as e: #invalid input data types
            tb = traceback.format_exc() #traceback info of the latest exception
            print(f"Error occurred:\n{tb}") 
            return Response(
                {"error": str(e), "traceback": tb.splitlines()[-1]},  
                status=status.HTTP_400_BAD_REQUEST
            )
        except grpc.RpcError as e:  #service unavailable
            logger.error("gRPC error: %s", e)
            return Response({"error": "Payment service unavailable"}, status=status.HTTP_502_BAD_GATEWAY)
        except Exception as e: #unexpected errors,db connection errors
            logger.exception("Unexpected error")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            client.close()      

class InitiatePaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated,IsStudent]

    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student_fee_id = serializer.validated_data['student_fee_id']
        gateway = serializer.validated_data['gateway']

        if not hasattr(request.user, 'student') or not request.user.student:
            print("ERROR: No student found in request.user")
            return Response(
                {"error": "Only students can initiate payments"},
                status=status.HTTP_403_FORBIDDEN,
            )

        student_id = request.user.student.id
        client = PaymentGRPCClient()
        try:   
            response = client.initiate_payment(
                student_fee_id=int(student_fee_id),
                student_id=student_id,
                gateway=gateway,
            )
            
            print(f"Payment gRPC response: {response}")
            
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
            print(f"Payment gRPC Error: {e.code()}: {e.details()}")
            return Response(
                {"error": f"Payment service error: {e.details()}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            client.close()
        
class SimulateRazorpayPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated,IsStudent]

    def post(self, request):
        def post(self, request):
            try:
                serializer = SimulateRazorpayPaymentSerializer(data=request.data)
                serializer.is_valid(raise_exception=True)
            except Exception as e:
                return Response(
                    {"error": f"Invalid input: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
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
                status=status.HTTP_502_BAD_GATEWAY
            )

class VerifyRazorpayPaymentView(APIView):
    permission_classes = [permissions.IsAuthenticated,IsStudent] 

    def post(self, request):
        payment_id = request.data.get("payment_id")
        razorpay_order_id = request.data.get("razorpay_order_id")
        razorpay_payment_id = request.data.get("razorpay_payment_id")
        razorpay_signature = request.data.get("razorpay_signature")

        if not all([payment_id, razorpay_order_id, razorpay_payment_id, razorpay_signature]):
            return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

        if not hasattr(request.user, "student") or not request.user.student:
            return Response({"error": "Only students can verify payments"}, status=403)

        student_id = request.user.student.id
        pay_client = PaymentGRPCClient()
        try:
            verify_response = pay_client.verify_payment(
                payment_id=int(payment_id),
                razorpay_order_id=razorpay_order_id,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature
            )

            if verify_response.message != "Payment verified successfully":
                return Response({"error": verify_response.message}, status=status.HTTP_400_BAD_REQUEST)

            receipt_response = pay_client.generate_receipt(
                payment_id=int(payment_id),
                student_id=student_id
            )

            return Response(
                {
                    "message": receipt_response.message,
                    "receipt_url": receipt_response.receipt_url
                },
                status=status.HTTP_200_OK
            )

        except grpc.RpcError as e:
            return Response({"error": e.details()}, status=status.HTTP_502_BAD_GATEWAY)