import pika
import json
import os
RABBITMQ_HOST = 'localhost'  
EXCHANGE_NAME = 'exam_events'

def publish_event(event_data, exchange="exam_events"):#event_data is a python dict
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))#opens TCP Connection to rabbitmq with host
        #channel created , publishing and consuming happens through channel
        channel = connection.channel()
        #exchange is declared and type is fanout , msg delivered to all queues
        channel.exchange_declare(exchange=exchange, exchange_type='fanout')
        #sends the mesg to the exchange with empty routing key
        channel.basic_publish(
            exchange=exchange,
            routing_key='',
            body=json.dumps(event_data)#converts python dict to string
        )
        connection.close()
        print(f"Published event: {event_data}")
    except Exception as e:
        print(f"Failed to publish event: {e}")