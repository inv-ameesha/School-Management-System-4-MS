from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import FeeStructure,StudentFee,Payment

class FeeAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeStructure
        fields = ['grade', 'academic_year', 'base_fee', 'due_date', 'fine_per_day']

class InitiatePaymentSerializer(serializers.Serializer):
    student_fee_id = serializers.IntegerField()
    gateway = serializers.ChoiceField(choices=["razorpay", "offline"])

class SimulateRazorpayPaymentSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    razorpay_order_id = serializers.CharField(max_length=100)

