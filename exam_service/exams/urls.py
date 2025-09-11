from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExamCreateView, AssignExamView, ExamAssignView, AttemptExamView,
    AssignedExamsListView,ExamDetailView
)
from django.conf.urls.static import static
from django.conf import settings
from rest_framework_simplejwt.views import TokenRefreshView
from .views import TeacherCreatedExamsView


urlpatterns = [
    path('exams/create/', ExamCreateView.as_view(), name='exam-create'),
    path('exams/assign/', AssignExamView.as_view(), name='exam-assign'),
    path('exams/assigned/', AssignedExamsListView.as_view(), name='exam-assigned'),
    path('exams/<int:exam_id>/attempt/', AttemptExamView.as_view(), name='exam-attempt'),
    path('exams/created-by-me/', TeacherCreatedExamsView.as_view(), name='teacher-created-exams'),
    path('exams/<int:pk>/', ExamDetailView.as_view(), name='exam-detail'),
]
