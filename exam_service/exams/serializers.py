from .models import Exam, Question, ExamAssignment, StudentExamAttempt, StudentAnswer
from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError, AuthenticationFailed

class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option']

class ExamSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True)

    class Meta:
        model = Exam
        fields = ['id', 'title', 'subject', 'date', 'duration', 'questions']

    def create(self, validated_data):
        teacher_user = validated_data.pop('teacher', None)
        if not teacher_user:
            request = self.context.get('request')
            teacher_user = request.user if request else None
        
        if not teacher_user or not hasattr(teacher_user, 'teacher'):
            raise serializers.ValidationError("Only teachers can create exams.")

        questions_data = validated_data.pop('questions',[])
        exam = Exam.objects.create(teacher=teacher_user, **validated_data)  
        for question_data in questions_data:
            Question.objects.create(exam=exam, **question_data)


class ExamAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAssignment
        fields = ['id', 'exam', 'student']

class StudentAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAnswer
        fields = ['question', 'selected_option']

class StudentExamAttemptSerializer(serializers.ModelSerializer):
    answers = StudentAnswerSerializer(many=True, write_only=True)

    class Meta:
        model = StudentExamAttempt
        fields = ['exam', 'student', 'answers']
        read_only_fields = ['start_time', 'submitted', 'score']

    def create(self, validated_data):
        answers_data = validated_data.pop('answers')
        student = validated_data.pop('student', None)
        attempt = StudentExamAttempt.objects.create(student=student, **validated_data)
        for answer_data in answers_data:
            StudentAnswer.objects.create(attempt=attempt, **answer_data)
        return attempt
