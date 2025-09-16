# payments/validators.py
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import FeeStructure, StudentFee, Payment

def validate_fee_structure_data(grade, academic_year, base_fee, due_date, fine_per_day):
    if grade is None or grade <= 0:
        raise ValidationError("Grade must be a positive integer")
    if not academic_year:
        raise ValidationError("Academic year is required")
    if base_fee is None or base_fee <= 0:
        raise ValidationError("Base fee must be greater than 0")
    if fine_per_day is None or fine_per_day < 0:
        raise ValidationError("Fine per day must be 0 or greater")
    if due_date < timezone.now().date():
        raise ValidationError("Due date cannot be in the past")

def validate_student_fee(student_id, fee_structure):
    if student_id is None or student_id <= 0:
        raise ValidationError("Student ID must be a valid positive integer")
    if not isinstance(fee_structure, FeeStructure):
        raise ValidationError("Invalid FeeStructure reference")

def validate_payment(student_fee, gateway, amount):
    if not isinstance(student_fee, StudentFee):
        raise ValidationError("Invalid StudentFee reference")
    if gateway not in ["razorpay", "offline"]:
        raise ValidationError(f"Unsupported gateway: {gateway}")
    if amount <= 0:
        raise ValidationError("Payment amount must be greater than 0")
