from rest_framework.permissions import BasePermission

class IsTeacher(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and not request.user.is_superuser

class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, "student") 
        