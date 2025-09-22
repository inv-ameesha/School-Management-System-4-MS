import logging
from types import SimpleNamespace
from django.conf import settings
from rest_framework import authentication, exceptions
from rest_framework_simplejwt.backends import TokenBackend

from payments.user_client import UserGRPCClient  # Adjust import according to your project
import grpc

logger = logging.getLogger(__name__)

class RemoteUser(SimpleNamespace):
    """
    Represents the authenticated user inside payment_service.
    Can have teacher and student attributes if applicable.
    """
    def __init__(self, id, username=None, email=None, teacher=None, student=None):
        super().__init__()
        self.id = id
        self.username = username or f'user_{id}'
        self.email = email
        self.is_authenticated = True
        self.teacher = teacher
        self.student = student


class UserServiceJWTAuthentication(authentication.BaseAuthentication):
    """
    Custom authentication class for payment_service.
    Validates JWT from user_service and optionally fetches teacher/student info via gRPC.
    """
    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != b'bearer':
            return None  # DRF will treat this as no authentication provided
        if len(header) == 1:
            raise exceptions.AuthenticationFailed("Invalid token header. No credentials provided.")

        token = header[1].decode()

        # Decode JWT token issued by user_service
        try:
            backend = TokenBackend(
                algorithm=getattr(settings, 'SIMPLE_JWT', {}).get('ALGORITHM', 'HS256'),
                signing_key=getattr(settings, 'SIMPLE_JWT', {}).get('SIGNING_KEY', settings.SECRET_KEY),
            )
            payload = backend.decode(token, verify=True)
        except Exception:
            raise exceptions.AuthenticationFailed("Invalid token")

        user_id = payload.get('user_id') or payload.get('userId') or payload.get('sub')
        if not user_id:
            raise exceptions.AuthenticationFailed("user_id missing from token")

        # Prefer teacher_id/student_id claims if present
        teacher_id_claim = payload.get('teacher_id') or payload.get('teacherId')
        student_id_claim = payload.get('student_id') or payload.get('studentId')

        if teacher_id_claim or student_id_claim:
            teacher = SimpleNamespace(id=int(teacher_id_claim)) if teacher_id_claim else None
            student = SimpleNamespace(id=int(student_id_claim)) if student_id_claim else None
            remote_user = RemoteUser(id=int(user_id), teacher=teacher, student=student)
        else:
            # Fallback: fetch user info from user_service via gRPC
            client = UserGRPCClient()
            try:
                teacher = None
                student = None

                # Attempt teacher lookup
                try:
                    teacher_resp = client.get_teacher_by_user(user_id)
                    if getattr(teacher_resp, 'teacher_id', 0):
                        teacher = SimpleNamespace(
                            id=getattr(teacher_resp, 'teacher_id', None),
                            first_name=getattr(teacher_resp, 'first_name', None),
                            last_name=getattr(teacher_resp, 'last_name', None),
                            email=getattr(teacher_resp, 'email', None),
                        )
                except grpc.RpcError as e:
                    logger.info("Teacher lookup error for user_id=%s: %s", user_id, getattr(e, 'details', str(e)))

                # Attempt student lookup
                try:
                    student_resp = client.get_student_by_user(user_id)
                    if getattr(student_resp, 'student', None) and getattr(student_resp.student, 'student_id', 0):
                        student = SimpleNamespace(
                            id=getattr(student_resp.student, 'student_id', None),
                            first_name=getattr(student_resp.student, 'first_name', None),
                            last_name=getattr(student_resp.student, 'last_name', None),
                            email=getattr(student_resp.student, 'email', None),
                            grade=getattr(student_resp.student, 'grade', None),
                        )
                except grpc.RpcError as e:
                    if getattr(e, 'code', lambda: None)() == grpc.StatusCode.NOT_FOUND:
                        logger.debug("No student for user_id=%s", user_id)
                    else:
                        logger.info("Student lookup error for user_id=%s: %s", user_id, getattr(e, 'details', str(e)))

                remote_user = RemoteUser(id=int(user_id), teacher=teacher, student=student)
            finally:
                try:
                    client.close()
                except Exception:
                    pass

        return (remote_user, token)
