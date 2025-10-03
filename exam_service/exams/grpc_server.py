import logging
logging.basicConfig(level=logging.INFO)
import grpc
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'exam_service.settings')
django.setup()
from concurrent import futures
import time
from .models import Exam,ExamAssignment,StudentExamAttempt
import exam_pb2
import exam_pb2_grpc
from exam_pb2 import ExamResponse, ListExamsResponse, CreateExamResponse , AssignExamResponse,AttemptExamResponse
from exam_pb2_grpc import ExamServiceServicer, add_ExamServiceServicer_to_server
from django.utils import timezone
from messaging.publisher import publish_event

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
        try:
            exam = Exam.objects.create(
                title=request.title,
                subject=request.subject,
                date=request.date,
                duration=request.duration,
                teacher_id=request.teacher_id            
            )
            return CreateExamResponse(exam_id=exam.id, message="Exam created successfully")
        except Exception as e:
            logging.error(f"Error in CreateExam: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return CreateExamResponse()
    
    def AssignExam(self, request, context):
        #context = rpc call state
        try:
            exam = Exam.objects.get(id=request.exam_id)#model exist here
        except Exam.DoesNotExist:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Exam not found")
            return AssignExamResponse()

        assigned_count = 0
        skipped = []

        for sid in request.student_id:
            try:
                # Store only student_id
                ExamAssignment.objects.get_or_create(exam=exam, student_id=sid)
                assigned_count += 1
            except Exception as e:
                skipped.append(sid)
                # logging.error(f"Error assigning exam {exam.id} to student {sid}: {e}")
                continue

        # After all assignments, publish event
        if assigned_count > 0:
            publish_event({
                "event": "students_allocated",
                "exam_id": exam.id,
                "student_ids": list(request.student_id),
                "message": f"{assigned_count} students allocated to exam {exam.id}"
            })

        message = f"Exam assigned to {assigned_count} students."
        if skipped:
            message += f" Skipped IDs: {skipped}"

        return AssignExamResponse(message=message)

    def GetExamsByStudent(self, request, context):
        response = exam_pb2.ListExamsResponse()
        student_id = request.student_id

        assignments = ExamAssignment.objects.filter(student_id=student_id)

        attempted_ids = StudentExamAttempt.objects.filter(
            student_id=student_id, submitted=1
        ).values_list("exam_id", flat=True)

        for assignment in assignments:
            exam = assignment.exam
            if exam.id in attempted_ids:
                continue  # skip already attempted exams

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

    def AttemptExam(self, request, context):
        try:
            try:
                exam = Exam.objects.get(id=request.exam_id)
            except Exam.DoesNotExist:
                context.set_code(grpc.StatusCode.NOT_FOUND)
                context.set_details("Exam not found")
                return exam_pb2.AttemptExamResponse(message="Exam not found")

            if StudentExamAttempt.objects.filter(
                student_id=request.student_id,
                exam=exam
            ).exists():
                context.set_code(grpc.StatusCode.ALREADY_EXISTS)
                context.set_details("Exam already submitted")
                return exam_pb2.AttemptExamResponse(message="Exam already submitted")

            # Save attempt
            StudentExamAttempt.objects.create(
                student_id=request.student_id,
                exam=exam,
                score=request.score,
                started_at=timezone.now(),
                submitted=1
            )

            return exam_pb2.AttemptExamResponse(
                message="Exam submitted successfully"
            )

        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return exam_pb2.AttemptExamResponse(message="Error submitting exam")

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