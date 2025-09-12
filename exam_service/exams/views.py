from django.shortcuts import render
from .models import Teacher, Student ,Payment, Exam , Question, ExamAssignment, StudentExamAttempt, StudentAnswer
from .serializers import (
   ExamSerializer,
    ExamAssignmentSerializer,StudentExamAttemptSerializer
)
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from rest_framework.generics import RetrieveAPIView
from django.contrib.auth.models import User
from .models import Student
from rest_framework import status

class TeacherCreatedExamsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        exams = Exam.objects.filter(teacher=request.user.teacher)
        serializer = ExamSerializer(exams, many=True)
        return Response(serializer.data)

# class ExamCreateView(generics.CreateAPIView):
#     serializer_class = ExamSerializer
#     permission_classes = [permissions.IsAuthenticated]

#     def perform_create(self, serializer):
#         serializer.save(teacher=self.request.user)

class AssignExamView(generics.CreateAPIView):
    serializer_class = ExamAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        exam_id = request.data.get('exam')
        student_ids = request.data.get('students') 

        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=404)

        for sid in student_ids:
            try:
                student_obj = Student.objects.get(id=sid)
                # Assign exam to the student object
                ExamAssignment.objects.get_or_create(exam=exam, student=student_obj)
            except Student.DoesNotExist:
                return Response(f"Student with ID {sid} does not exist. Skipping.")

        return Response({'message': 'Exam assigned successfully'}, status=201)


# Student lists all exams assigned to them
class ExamAssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        exam_id = request.data.get('exam_id')
        student_id = request.data.get('student_id')

        try:
            exam = Exam.objects.get(id=exam_id)
            student = Student.objects.get(id=student_id)

            if student.assigned_teacher.user.id == exam.teacher.id:
                ExamAssignment.objects.create(exam=exam, student=student)
                return Response({"detail": "Exam assigned successfully."})
            else:
                return Response({"detail": "You can only assign your exam to your students."}, status=400)

        except Exam.DoesNotExist:
            return Response({"detail": "Exam not found."}, status=404)
        except Student.DoesNotExist:
            return Response({"detail": "Student not found."}, status=404)

class AttemptExamView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        user = request.user
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=404)

        # Check if already attempted
        student = Student.objects.get(user=user)
        if StudentExamAttempt.objects.filter(student=student, exam=exam).exists():
            return Response({'message': 'Exam already submitted'}, status=403)

        # Create the attempt
        StudentExamAttempt.objects.create(student=user, exam=exam, started_at=timezone.now())
        return Response({'message': 'Exam submitted successfully'}, status=201)

class AssignedExamsListView(generics.ListAPIView):
    serializer_class = ExamAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        try:
            student = Student.objects.get(user=user)
            print(student)
        except Student.DoesNotExist:
            return ExamAssignment.objects.none()
        assignments = ExamAssignment.objects.filter(student=student)  # must use user
        valid_assignments = []
        for assignment in assignments:
            exam = assignment.exam
            # Only include if NOT already attempted
            if StudentExamAttempt.objects.filter(exam=exam, student=user).exists():
                continue
            # Only include if NOT expired
            exam_start_time = assignment.assigned_at
            exam_end_time = exam_start_time + timezone.timedelta(minutes=exam.duration)
            if timezone.now() > exam_end_time:
                continue
            # If not attempted and not expired, include in the list
            valid_assignments.append(assignment.id)
        return ExamAssignment.objects.filter(id__in=valid_assignments)

class ExamDetailView(RetrieveAPIView):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
