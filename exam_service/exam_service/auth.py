import logging
from types import SimpleNamespace
from venv import logger
from django.conf import settings
from rest_framework import authentication, exceptions
from rest_framework_simplejwt.backends import TokenBackend

from exams.grpc_client import UserGRPCClient
import grpc

class RemoteUser(SimpleNamespace):
    def __init__(self, id, username=None, email=None, teacher=None):
        super().__init__()
        self.id = id
        self.username = username or f'user_{id}'
        self.email = email
        self.is_authenticated = True
        self.teacher = teacher
        self.student = None


class UserServiceJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != b'bearer':
            return None
        if len(header) == 1:
            raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')

        token = header[1].decode()

        try:
            backend = TokenBackend(
                algorithm=getattr(settings, 'SIMPLE_JWT', {}).get('ALGORITHM', 'HS256'),
                signing_key=getattr(settings, 'SIMPLE_JWT', {}).get('SIGNING_KEY', settings.SECRET_KEY),
            )
            payload = backend.decode(token, verify=True)
        except Exception as e:
            raise exceptions.AuthenticationFailed('Invalid token')

        user_id = payload.get('user_id') or payload.get('userId') or payload.get('sub')
        if not user_id:
            raise exceptions.AuthenticationFailed('user_id missing from token')

        # Try to extract teacher_id/student_id directly from token claims to avoid an extra gRPC call
        teacher_id_claim = payload.get('teacher_id') or payload.get('teacherId')
        student_id_claim = payload.get('student_id') or payload.get('studentId')
        # If the token already contains teacher_id or student_id claims, prefer them
        if teacher_id_claim or student_id_claim:
            teacher = None
            if teacher_id_claim:
                teacher = SimpleNamespace(id=int(teacher_id_claim))
            remote_user = RemoteUser(id=int(user_id), teacher=teacher)
            if student_id_claim:
                # attach a minimal student object for downstream views
                remote_user.student = SimpleNamespace(id=int(student_id_claim))
        else:
            # Fetch remote user/teacher details via gRPC as fallback
            # Always fetch authoritative role info from user_service
            client = UserGRPCClient(timeout_seconds=5)
            try:
                teacher = None
                student = None

                # Try teacher lookup
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
                    # log but don't raise; we'll still try to fetch student
                    logger.info("teacher lookup error for user_id=%s: %s", user_id, getattr(e, 'details', lambda: str(e))())

                # Try student lookup (new RPC)
                try:
                    student_resp = client.get_student_by_user(user_id)
                    # if found, attach
                    if getattr(student_resp, 'student', None) and getattr(student_resp.student, 'student_id', 0):
                        student = SimpleNamespace(
                            id=getattr(student_resp.student, 'student_id', None),
                            first_name=getattr(student_resp.student, 'first_name', None),
                            last_name=getattr(student_resp.student, 'last_name', None),
                            email=getattr(student_resp.student, 'email', None),
                            grade=getattr(student_resp.student, 'grade', None),
                        )
                except grpc.RpcError as e:
                    # Not found is normal; ignore NOT_FOUND: student stays None
                    code = getattr(e, 'code', lambda: None)()
                    if code == grpc.StatusCode.NOT_FOUND:
                        logger.debug("No student for user_id=%s", user_id)
                    else:
                        logger.info("student lookup error for user_id=%s: %s", user_id, getattr(e, 'details', lambda: str(e))())

                # Build RemoteUser with both attachments
                remote_user = RemoteUser(id=int(user_id), username=None, email=None, teacher=teacher)
                remote_user.student = student

            finally:
                try:
                    client.close()
                except Exception:
                    pass

        # Second item in tuple is auth info (we can return token)
        return (remote_user, token)
