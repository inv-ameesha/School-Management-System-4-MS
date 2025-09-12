import logging
logging.basicConfig(level=logging.INFO)
import grpc
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exam_service.settings')
django.setup()
from concurrent import futures
import time
from .models import Exam,ExamAssignment
from exam_pb2 import ExamResponse, ListExamsResponse, CreateExamResponse , AssignExamResponse
from exam_pb2_grpc import ExamServiceServicer, add_ExamServiceServicer_to_server

class ExamService(ExamServiceServicer):
    def GetExam(self, request, context):
        # logging.info(f"Received GetExam request for ID: {request.exam_id}")
        try:
            exam = Exam.objects.get(id=request.exam_id)
            teacher_id = getattr(exam, 'teacher_id', None)
            if hasattr(exam, 'teacher') and hasattr(exam.teacher, 'id'):
                teacher_id = exam.teacher.id
            elif teacher_id is None:
                teacher_id = 0  # Default value if no teacher_id
            return ExamResponse(
                exam_id=exam.id,
                title=exam.title,
                subject=exam.subject,
                date=str(exam.date),
                duration=exam.duration,
                teacher_id=teacher_id
            )
        except Exam.DoesNotExist:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details('Exam not found')
            return ExamResponse()
        except AttributeError as e:
            # logging.error(f"AttributeError in GetExam: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return ExamResponse()

    def ListExams(self, request, context):
        exams = Exam.objects.all()
        response = ListExamsResponse()
        for exam in exams:
            teacher_id = getattr(exam, 'teacher_id', None)
            if hasattr(exam, 'teacher') and hasattr(exam.teacher, 'id'):
                teacher_id = exam.teacher.id
            response.exams.add(
                exam_id=exam.id,
                title=exam.title,
                subject=exam.subject,
                date=str(exam.date),
                duration=exam.duration,
                teacher_id=teacher_id or 0
            )
        return response

    def CreateExam(self, request, context):
        # Prepare data for serializer
        exam_data = {
            'title': request.title,
            'subject': request.subject,
            'date': request.date,
            'duration': request.duration,
        }

        # Resolve teacher object
        try:
            teacher = Teacher.objects.get(id=request.teacher_id)
        except Teacher.DoesNotExist:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Teacher not found")
            return CreateExamResponse()

        #  serializer for validation and creation
        serializer = ExamSerializer(data=exam_data, context={'request': None})
        serializer.initial_data['teacher'] = teacher  # inject teacher object

        # Validate input
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(str(e))
            return CreateExamResponse()

        try:
            exam = serializer.save()
            return CreateExamResponse(exam_id=exam.id, message="Exam created successfully")
        except Exception as e:
            logging.error(f"Error creating exam: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return CreateExamResponse()
    
    def AssignExam(self, request, context):
        try:
            exam = Exam.objects.get(id=request.exam_id)
        except Exam.DoesNotExist:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Exam not found")
            return AssignExamResponse()

        assigned_count = 0
        skipped = []

        for sid in request.student_ids:
            try:
                # Store only student_id
                ExamAssignment.objects.get_or_create(exam=exam, student_id=sid)
                assigned_count += 1
            except Exception as e:
                skipped.append(sid)
                logging.error(f"Error assigning exam {exam.id} to student {sid}: {e}")
                continue

        message = f"Exam assigned to {assigned_count} students."
        if skipped:
            message += f" Skipped IDs: {skipped}"

        return AssignExamResponse(message=message)

    def GetExamsByStudent(self, request, context):
        response = ListExamsResponse()
        assignments = ExamAssignment.objects.filter(student_id=request.student_id)

        for assignment in assignments:
            exam = assignment.exam
            response.exams.add(
                exam_id=exam.id,
                title=exam.title,
                subject=exam.subject,
                date=str(exam.date),
                duration=exam.duration,
                teacher_id=exam.teacher_id
            )
        return response

    def GetExamsByTeacher(self, request, context):
        response = ListExamsResponse()
        exams = Exam.objects.filter(teacher_id=request.teacher_id)

        for exam in exams:
            response.exams.add(
                exam_id=exam.id,
                title=exam.title,
                subject=exam.subject,
                date=str(exam.date),
                duration=exam.duration,
                teacher_id=exam.teacher_id
            )
        return response

def serve():
    try:
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
        add_ExamServiceServicer_to_server(ExamService(), server)
        server.add_insecure_port('0.0.0.0:50051')
        logging.info("gRPC server starting on 0.0.0.0:50051")
        server.start()
        print("gRPC server started on port 50051")
        server.wait_for_termination()
    except Exception as e:
        logging.error(f"Server failed to start: {e}")
        raise

if __name__ == '__main__':
    serve()