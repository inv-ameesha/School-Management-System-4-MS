from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import FeeStructure,StudentFee,Payment

class FeeAllocationSerializer(serializers.Serializer):
    grade = serializers.IntegerField()
    academic_year = serializers.CharField(max_length=20)
    base_fee = serializers.FloatField()
    due_date = serializers.DateField(format="%Y-%m-%d", input_formats=["%Y-%m-%d"])
    fine_per_day = serializers.FloatField()

class InitiatePaymentSerializer(serializers.Serializer):
    student_fee_id = serializers.IntegerField()
    gateway = serializers.ChoiceField(choices=["razorpay", "offline"])

class SimulateRazorpayPaymentSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    razorpay_order_id = serializers.CharField(max_length=100)

class VerifyRazorpayPaymentSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    razorpay_order_id = serializers.CharField(max_length=100)
    razorpay_payment_id = serializers.CharField(max_length=100)
    razorpay_signature = serializers.CharField(max_length=256)