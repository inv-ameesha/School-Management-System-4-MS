from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.conf.urls.static import static
from django.conf import settings
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    ExamCreateView,
    AssignExamView,
    TeacherCreatedExamsView,
    StudentAssignedExamsView,AttemptExamView
)
urlpatterns = [
    path("exams", ExamCreateView.as_view(), name="create-exam"),
    path('exams/assign/', AssignExamView.as_view(), name='exam-assign'),
    path("exams/teacher/", TeacherCreatedExamsView.as_view(), name="teacher-exams"),
    path("exams/student/", StudentAssignedExamsView.as_view(), name="student-exams"),
    path('exam/attempt/', AttemptExamView.as_view(), name='exam-attempt'),
]
