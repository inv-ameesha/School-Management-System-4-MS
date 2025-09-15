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
]
