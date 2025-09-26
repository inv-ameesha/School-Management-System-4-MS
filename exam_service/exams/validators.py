from datetime import datetime
from rest_framework import serializers

def validate_subject(subject):
    if not subject.isalpha():
        raise serializers.ValidationError("Subject must contain only alphabets")
    
def validate_date(date):
    if date < datetime.now().date():
        raise serializers.ValidationError("Exam date cannot be in the past")

