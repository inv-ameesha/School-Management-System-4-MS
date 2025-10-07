from .models import Exam, Question, ExamAssignment, StudentExamAttempt, StudentAnswer
from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from .validators import *
from rest_framework.validators import UniqueTogetherValidator

class ExamSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    subject = serializers.CharField(max_length=100, validators=[validate_subject])
    date = serializers.DateField(validators=[validate_date])
    duration = serializers.IntegerField()
    teacher_id = serializers.IntegerField()

    def validate_duration(self, value):
        if value <= 0:
            raise serializers.ValidationError("Duration must be a positive integer")
        return value

class ExamAssignmentSerializer(serializers.ModelSerializer):
    exam_id = serializers.IntegerField()
    student_id = serializers.ListField(child=serializers.IntegerField())

    def validate_exam_id(self, value):
        try:
            Exam.objects.get(id=value)
        except Exam.DoesNotExist:
            raise serializers.ValidationError("Exam does not exist")
        return value

    class Meta:
        model = ExamAssignment
        fields = ['id', 'exam_id', 'student_id']
        validators = [
            UniqueTogetherValidator(
                queryset=ExamAssignment.objects.all(),
                fields=['exam_id', 'student_id'],
                message='Exam already assigned'
            )
        ]

class ExamAttemptSerializer(serializers.ModelSerializer):
    score = serializers.IntegerField()
    exam_id = serializers.IntegerField()
    class Meta:
        model = StudentExamAttempt
        fields = ['score','exam_id']
        