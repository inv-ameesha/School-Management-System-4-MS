import pika, json
import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "payment_service.settings")
django.setup()
from payments.models import StudentFee, FeeStructure
from datetime import date

def callback(ch, method, properties, body):
    data = json.loads(body)
    student_id = data["student_id"]
    grade = data["grade"]
    academic_year = data["academic_year"]

    print(f"[RabbitMQ] Creating StudentFee for student {student_id}...")

    try:
        fee_structure = FeeStructure.objects.get(grade=grade, academic_year=academic_year)
        student_fee = StudentFee.objects.create(
            student_id=student_id,
            fee_structure=fee_structure,
            due_date=fee_structure.due_date,
            total_amount=fee_structure.base_fee,
            status="pending"
        )
        print(f"[Payment] StudentFee created: {student_fee.id} for student {student_id}")

        ch.basic_ack(delivery_tag=method.delivery_tag)  # acknowledge message,removes from q
    except FeeStructure.DoesNotExist:
        print(f"[ERROR] FeeStructure not found for grade {grade}, year {academic_year}")
    except Exception as e:
        print(f"[ERROR] Failed to create StudentFee for student {student_id}: {str(e)}")

def start_consumer():
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
    channel = connection.channel()
    channel.queue_declare(queue='student_fee_queue', durable=True)#msg exist even if rabbit mq restarts

    channel.basic_qos(prefetch_count=1)  # fair dispatch
    channel.basic_consume(queue='student_fee_queue', on_message_callback=callback)

    print("[RabbitMQ] Waiting for student messages...")
    channel.start_consuming()

if __name__ == "__main__":
    start_consumer()
