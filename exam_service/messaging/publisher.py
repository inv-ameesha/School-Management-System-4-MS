import pika
import json

RABBITMQ_HOST = 'localhost'  
EXCHANGE_NAME = 'exam_events'

def publish_event(event_data, exchange="exam_events"):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        channel.exchange_declare(exchange=exchange, exchange_type='fanout')
        channel.basic_publish(
            exchange=exchange,
            routing_key='',
            body=json.dumps(event_data)
        )
        connection.close()
        print(f"Published event: {event_data}")
    except Exception as e:
        print(f"Failed to publish event: {e}")