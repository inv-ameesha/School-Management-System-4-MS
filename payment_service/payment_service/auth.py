import logging
from types import SimpleNamespace
from django.conf import settings
from rest_framework import authentication, exceptions
from rest_framework_simplejwt.backends import TokenBackend

from payments.user_client import UserGRPCClient
import grpc

logger = logging.getLogger(__name__)

class RemoteUser(SimpleNamespace):
    def __init__(self, id, username=None, email=None,role=None, teacher=None, student=None):
        super().__init__()
        self.id = id
        self.username = username or f'user_{id}'
        self.email = email
        self.role = role
        self.is_authenticated = True
        self.teacher = teacher
        self.student = student

    # @property
    # def is_staff(self):
    #     return self.role == "admin"
        
class UserServiceJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        
        # Check if Authorization header exists
        auth_header = authentication.get_authorization_header(request)
        print(f"DEBUG: Authorization header: {auth_header}")
        header = auth_header.split()
        print(f"DEBUG: Authorization header parts: {header}")
        if not header:
            return None
            
        if header[0].lower() != b'bearer':
            return None
            
        if len(header) == 1:
            print("DEBUG: Bearer found but no token")
            raise exceptions.AuthenticationFailed("Invalid token header. No credentials provided.")

        token = header[1].decode()
        print(f"DEBUG: Extracted token: {token[:50]}...")  # Show first 50 chars

        # Try to decode JWT
        try:
            print("DEBUG: Attempting to decode JWT...")
            
            # Check what JWT settings we have
            simple_jwt_settings = getattr(settings, 'SIMPLE_JWT', {})
            algorithm = simple_jwt_settings.get('ALGORITHM', 'HS256')
            signing_key = simple_jwt_settings.get('SIGNING_KEY', settings.SECRET_KEY)
            
            print(f"DEBUG: Using algorithm: {algorithm}")
            print(f"DEBUG: Using signing key (first 10 chars): {str(signing_key)[:10]}...")
            
            backend = TokenBackend(
                algorithm=algorithm,
                signing_key=signing_key,
            )
            
            payload = backend.decode(token, verify=True)
            print(f"DEBUG: Successfully decoded payload: {payload}")
            
        except Exception as e:
            print(f"DEBUG: Token decode failed with error: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"DEBUG: Full traceback: {traceback.format_exc()}")
            raise exceptions.AuthenticationFailed(f"Invalid token: {str(e)}")

        # Extract user_id
        user_id = payload.get('user_id')
        role = payload.get('role')
        print(f"DEBUG: Extracted user_id: {user_id}")
        
        if not user_id:
            print("DEBUG: No user_id found in token")
            raise exceptions.AuthenticationFailed("user_id missing from token")

        # Check for direct claims
        teacher_id_claim = payload.get('teacher_id') or payload.get('teacherId')
        student_id_claim = payload.get('student_id') or payload.get('studentId')
        
        print(f"DEBUG: Teacher ID claim: {teacher_id_claim}")
        print(f"DEBUG: Student ID claim: {student_id_claim}")

        if teacher_id_claim or student_id_claim:
            teacher = SimpleNamespace(id=int(teacher_id_claim)) if teacher_id_claim else None
            student = SimpleNamespace(id=int(student_id_claim)) if student_id_claim else None
            remote_user = RemoteUser(id=int(user_id),teacher=teacher, student=student)
            print(f"DEBUG: Created user from claims: {remote_user}")
        else:
            print("DEBUG: No direct claims, querying user service via gRPC...")
            
            
            # gRPC lookup
            client = UserGRPCClient()
            try:
                teacher = None
                student = None

                if(teacher_id_claim):
                    try:
                        print(f"DEBUG: Looking up teacher for user_id: {user_id}")
                        teacher_resp = client.get_teacher_by_user(user_id)
                        print(f"DEBUG: Teacher response: {teacher_resp}")
                        
                        if getattr(teacher_resp, 'teacher_id', 0):
                            teacher = SimpleNamespace(
                                id=getattr(teacher_resp, 'teacher_id', None),
                                first_name=getattr(teacher_resp, 'first_name', None),
                                last_name=getattr(teacher_resp, 'last_name', None),
                                email=getattr(teacher_resp, 'email', None),
                            )
                            print(f"DEBUG: Created teacher object: {teacher}")
                    except grpc.RpcError as e:
                        print(f"DEBUG: Teacher lookup gRPC error: {e.code()}: {e.details()}")

                if(student_id_claim):
                    try:
                        print(f"DEBUG: Looking up student for user_id: {user_id}")
                        student_resp = client.get_student_by_user(user_id)
                        print(f"DEBUG: Student response: {student_resp}")
                        
                        if getattr(student_resp, 'student', None) and getattr(student_resp.student, 'student_id', 0):
                            student = SimpleNamespace(
                                id=getattr(student_resp.student, 'student_id', None),
                                first_name=getattr(student_resp.student, 'first_name', None),
                                last_name=getattr(student_resp.student, 'last_name', None),
                                email=getattr(student_resp.student, 'email', None),
                                grade=getattr(student_resp.student, 'grade', None),
                            )
                            print(f"DEBUG: Created student object: {student}")
                    except grpc.RpcError as e:
                        print(f"DEBUG: Student lookup gRPC error: {e.code()}: {e.details()}")

                remote_user = RemoteUser(id=int(user_id),role=role , teacher=teacher, student=student)
                print(f"DEBUG: Created user from gRPC: {remote_user}")
                
            except Exception as e:
                print(f"DEBUG: Unexpected error during gRPC calls: {type(e).__name__}: {str(e)}")
                import traceback
                print(f"DEBUG: gRPC traceback: {traceback.format_exc()}")
                raise exceptions.AuthenticationFailed(f"User service error: {str(e)}")
            finally:
                try:
                    client.close()
                except Exception:
                    pass

        print(f"DEBUG: Final user object: ID={remote_user.id}, teacher={remote_user.teacher}, student={remote_user.student}")
        print("=== DEBUG: Authentication successful ===")
        return (remote_user, token)