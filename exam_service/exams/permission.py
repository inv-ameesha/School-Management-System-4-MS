from rest_framework.permissions import BasePermission

class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, "student")

class IsTeacher(BasePermission):
    def has_permission(self, request, view):
        return hasattr(request.user, "teacher")
    
class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"