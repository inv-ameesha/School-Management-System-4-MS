from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ImportStudentsCSV,
    TeacherViewSet, StudentViewSet,
    CustomTokenObtainPairView,ExamCreateView,AssignExamView,
    StudentAssignedExamsView,TeacherCreatedExamsView, FeeAllocationView,
    InitiatePaymentView, SimulateRazorpayPaymentView , VerifyRazorpayPaymentView,
    AttemptExamView
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
    path('fee-allocation/', FeeAllocationView.as_view(), name='fee-allocation'),
    path('pay/initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path("simulate/", SimulateRazorpayPaymentView.as_view(), name="simulate-payment"),
    path('pay/verify/', VerifyRazorpayPaymentView.as_view(), name='verify-payment'),
    
]