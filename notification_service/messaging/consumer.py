import pika
import json
import django
import os
import smtplib
import sys
from email.message import EmailMessage
import grpc
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from notification_service import user_service_pb2 as user_pb2, user_service_pb2_grpc as user_pb2_grpc

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "notification_service.notification_service.settings")
django.setup()

RABBITMQ_HOST = "localhost"

def send_email(to_email, subject, body):
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = 'ameesha468@gmail.com'
        msg['To'] = to_email
        msg.set_content(body)
        with smtplib.SMTP('smtp.gmail.com', 587) as server:#SMTP server by domain name and port
            server.starttls()
            server.login('ameesha468@gmail.com', 'pcnh tdoh elvb lety')  
            server.send_message(msg)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")

def get_students(student_ids):
    try:
        with grpc.insecure_channel('localhost:50053') as channel:
            # print(student_ids)
            stub = user_pb2_grpc.UserServiceStub(channel)
            response = stub.GetStudentsByIds(user_pb2.GetStudentsRequest(user_id=student_ids))
            return response.students
    except grpc.RpcError as e:
        print(f"gRPC error fetching students: {e}")
        return []

def callback(ch, method, properties, body):
    try:
        data = json.loads(body)
        if data.get("event") == "students_allocated":
            exam_id = data.get("exam_id")
            student_ids = data.get("student_ids", [])
            if not student_ids:
                print("No student IDs provided in event")
                return

            # Fetch student details via gRPC
            students = get_students(student_ids)
            for student in students:
                send_email(
                    to_email=student.email,
                    subject=f"New Exam Assigned: {exam_id}",
                    body=f"Dear {student.first_name},\nYou have been allocated to exam {exam_id}."
                )
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in message: {e}")
    except Exception as e:
        print(f"Error processing message: {e}")

connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))#rabbitmq connnection
channel = connection.channel()
channel.exchange_declare(exchange="exam_events", exchange_type="fanout")
channel.queue_declare(queue="notification_service")#q declaration
channel.queue_bind(exchange="exam_events", queue="notification_service")
channel.basic_consume(queue="notification_service", on_message_callback=callback, auto_ack=True)

print("Notification Service listening for student allocation events...")
channel.start_consuming()