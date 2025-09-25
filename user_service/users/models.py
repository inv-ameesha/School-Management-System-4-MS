from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    first_name=models.CharField(max_length=100)
    last_name=models.CharField(max_length=100)
    email=models.EmailField(unique=True)
    phone=models.IntegerField(default=0)
    subject=models.CharField(max_length=50)
    e_id=models.CharField(max_length=20,unique=True)
    doj=models.DateField()
    status=models.CharField(max_length=10,choices=[('Active','Active'),('Inactive','Inactive')])

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,related_name='student', null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15)
    roll_number = models.CharField(max_length=20, unique=True)
    grade = models.IntegerField(null=True, blank=True)  
    academic_year = models.CharField(max_length=20,null=True, blank=True)  
    date_of_birth = models.DateField()
    admission_date = models.DateField()
    status = models.CharField(max_length=10, choices=[('Active', 'Active'), ('Inactive', 'Inactive')])
    assigned_teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


