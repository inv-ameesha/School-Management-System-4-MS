from .models import Exam, Question, ExamAssignment, StudentExamAttempt, StudentAnswer
from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from .validators import *
from rest_framework.validators import UniqueTogetherValidator
class ExamSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=255)
    subject = serializers.CharField(max_length=100, validators=[validate_subject])
    date = serializers.DateField(validators=[validate_date])
    duration = serializers.IntegerField()
    class Meta:
        model = Exam
        fields = ['id', 'title', 'subject', 'date', 'duration']

class ExamAssignmentSerializer(serializers.ModelSerializer): 
    exam_id = serializers.IntegerField()
    student_id = serializers.ListField()

    class Meta:
        model = ExamAssignment
        fields = ['id', 'exam_id', 'student_id']
        validators = [
            UniqueTogetherValidator(
                queryset = ExamAssignment.objects.all(),
                fields=['exam_id','student_id'],
                message = 'Exam already assigned'
            )
        ]

class ExamAttemptSerializer(serializers.ModelSerializer):
    score = serializers.IntegerField()
    exam_id = serializers.IntegerField()
    class Meta:
        model = StudentExamAttempt
        fields = ['score','exam_id']
        