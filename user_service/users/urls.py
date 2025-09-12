from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ImportStudentsCSV,
    TeacherViewSet, StudentViewSet,
    CustomTokenObtainPairView,ExamCreateView,AssignExamView,
    StudentAssignedExamsView,TeacherCreatedExamsView
)
from django.conf.urls.static import static
from django.conf import settings
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register('teachers', TeacherViewSet)
router.register('students', StudentViewSet, basename='students')

urlpatterns = [
    path('', include(router.urls)),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('import/students/', ImportStudentsCSV.as_view(), name='import_students_csv'),
    path("exams/", ExamCreateView.as_view(), name="create-exam"),
    path('exams/assign/', AssignExamView.as_view(), name='exam-assign'),
    path("exams/teacher/", TeacherCreatedExamsView.as_view(), name="teacher-exams"),
    path("exams/student/", StudentAssignedExamsView.as_view(), name="student-exams"),
]