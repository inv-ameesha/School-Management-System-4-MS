from .models import Exam, Question, ExamAssignment, StudentExamAttempt, StudentAnswer
from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError, AuthenticationFailed
class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option']


class ExamSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True)#we can create a list of questions with the same object

    class Meta:
        model = Exam
        fields = ['id', 'title', 'subject', 'date', 'duration', 'questions']

    def create(self, validated_data):
        teacher_user = validated_data.pop('teacher', None)#gets the teacher info from the validated_data
        #since we does not pass 'teacher' through our frontend it might not understand that its teacher
        if not teacher_user:
            request = self.context.get('request')#so we will first fetch the request
            teacher_user = request.user if request else None#then will fetch the user
        
        if not teacher_user or not hasattr(teacher_user, 'teacher'):
            raise serializers.ValidationError("Only teachers can create exams.")

        questions_data = validated_data.pop('questions',[])#each question entered stored to validated_data , only that qstns are popped out
        exam = Exam.objects.create(teacher=teacher_user, **validated_data)  #creates exam assign a user(teacher) to it
        for question_data in questions_data:
            Question.objects.create(exam=exam, **question_data)#using all the questions created it will create an exam
        return exam


class ExamAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamAssignment
        fields = ['id', 'exam', 'student']

#ensures that student valid answer only received 
class StudentAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAnswer
        fields = ['question', 'selected_option']

#students submit entire exam with all answers
class StudentExamAttemptSerializer(serializers.ModelSerializer):
    answers = StudentAnswerSerializer(many=True, write_only=True)

    class Meta:
        model = StudentExamAttempt
        fields = ['exam', 'student', 'answers']
        read_only_fields = ['start_time', 'submitted', 'score']#not to be passed by the frontend,auto assigned

    def create(self, validated_data):
        answers_data = validated_data.pop('answers')#fetch each answer individually
        student = validated_data.pop('student', None)#fetch corresponding student also
        attempt = StudentExamAttempt.objects.create(student=student, **validated_data)#create an attempt
        for answer_data in answers_data:
            StudentAnswer.objects.create(attempt=attempt, **answer_data)#save all the answers to this attempt
        return attempt
