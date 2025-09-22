from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
     FeeAllocationView,
    InitiatePaymentView, SimulateRazorpayPaymentView , VerifyRazorpayPaymentView
)
from django.conf.urls.static import static
from django.conf import settings
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('fee-allocation/', FeeAllocationView.as_view(), name='fee-allocation'),
    path('pay/initiate/', InitiatePaymentView.as_view(), name='initiate-payment'),
    path("simulate/", SimulateRazorpayPaymentView.as_view(), name="simulate-payment"),
    path('pay/verify/', VerifyRazorpayPaymentView.as_view(), name='verify-payment'),
    
]