from rest_framework import serializers
from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Teacher, Student 
from django.db import transaction

class TeacherSerializer(serializers.ModelSerializer):
    #external fields of user table
    username = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(required=True)

    class Meta:
        model = Teacher#model specified
        fields = [
            'id', 'first_name', 'last_name', 'email', 'phone', 'subject',
            'e_id', 'doj', 'status', 'user',
            'username', 'password'
        ]
        read_only_fields = ['user', 'id']#auto assign user must not edit it

    def create(self, validated_data):
        #validated_data : dictionary which is auto created by rest framework,for create,update to store latest data
        #it is must in serializers else we need to fetch data like request.data which doesnot check for validation which extempts the usage of serailizers itself
        username = validated_data.pop('username')#pop done bcz its not a part of teacher model 
        password = validated_data.pop('password')
        email = validated_data.get('email')

        if User.objects.filter(username=username).exists():
            raise ValidationError({'username': 'This username is already taken.'})
        if User.objects.filter(email=email).exists():
            raise ValidationError({'email': 'This email is already registered.'})
        if Teacher.objects.filter(e_id=validated_data.get('e_id')).exists():
            raise ValidationError({'e_id': 'This e_id already exists.'})

        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password, email=email)
            validated_data['user'] = user#add the newly created teacher to the validated_data dictionary
            teacher =  Teacher.objects.create(**validated_data)#create teacher with username,pwd,email and all additional fields

        return teacher
    
class StudentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True)
    email = serializers.EmailField(required=True)
    assigned_teacher = serializers.PrimaryKeyRelatedField(
        queryset=Teacher.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Student
        fields = [
            'id', 'first_name', 'last_name', 'phone_number', 'roll_number',
            'grade','academic_year', 'date_of_birth', 'admission_date',
            'status', 'username', 'password', 'email', 'user', 'assigned_teacher'
        ]
        read_only_fields = ['user', 'id']

    def create(self, validated_data):
        username = validated_data.pop('username')
        password = validated_data.pop('password')
        email = validated_data.get('email')

        if User.objects.filter(username=username).exists():
            raise ValidationError({'username': 'This username is already taken.'})
        if User.objects.filter(email=email).exists():
            raise ValidationError({'email': 'This email is already registered.'})
        if Student.objects.filter(roll_number=validated_data.get('roll_number')).exists():
            raise ValidationError({'roll_number': 'Roll number already exists.'})

        with transaction.atomic():
            user = User.objects.create_user(username=username, password=password, email=email)
            validated_data['user'] = user
            student =  Student.objects.create(**validated_data)

        return student
    
    
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    role = serializers.CharField(required=False)
    #TokenObtainPairSerializer : generates access token,refresh token
    #this function used when some credentials like role,user_id etc are passed other than access token,refresh token
    def validate(self, attrs):#inbuilt method, auto-called when username,pwd SUBMITTED BY USER
        data = super().validate(attrs)#validates to generate access token,refresh token
        user = self.user#find the authenticated user

        # Determine role based on user properties
        #since the teacher,student model has a onetoone relation btw teachertable and user table where user table inturn creates a user.teacher option too
        if user.is_superuser:
            real_role = 'admin'
        elif hasattr(user, 'teacher'):
            real_role = 'teacher'
        elif hasattr(user, 'student'):
            real_role = 'student'
        else:
            real_role = 'unknown'

        requested_role = self.initial_data.get('role')#get the role which user entered
        if requested_role and requested_role != real_role:#if both roles doesn't match then error
            raise serializers.ValidationError(f"Role mismatch: You are '{real_role}', not '{requested_role}'.")

        data['role'] = real_role#adds to data to be returned during token response
        data['username'] = user.username
        data['email'] = user.email

        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        try:
            if hasattr(user, 'teacher') and user.teacher is not None:
                token['teacher_id'] = int(user.teacher.id)
        except Exception:
            pass
        try:
            if hasattr(user, 'student') and user.student is not None:
                token['student_id'] = int(user.student.id)
        except Exception:
            pass
        try:
            if user.is_superuser==1:
                token['role'] = 'admin'
            elif hasattr(user, 'teacher'):
                token['role'] = 'teacher'
            elif hasattr(user, 'student'): 
                token['role'] = 'student'
        except Exception:
            pass
        return token


