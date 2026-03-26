import json
import boto3
from botocore.exceptions import ClientError
from app.config import get_settings
from app.services.redis_indexer import indexer

settings = get_settings()


class SQSConsumer:
    def __init__(self):
        self.client = boto3.client(
            'sqs',
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.queue_url = settings.sqs_queue_url

    def process_message(self, message_body: str) -> bool:
        try:
            event = json.loads(message_body)
            event_type = event.get('event_type')
            data = event.get('data', {})
            accommodation = data.get('accommodation', {})
            
            accommodation_id = accommodation.get('id')
            
            if not accommodation_id:
                print(f"❌ No accommodation ID in message")
                return False

            if event_type == 'accommodation.created':
                return indexer.index_accommodation(accommodation_id, accommodation)
            
            elif event_type == 'accommodation.updated':
                return indexer.update_accommodation(accommodation_id, accommodation)
            
            elif event_type == 'accommodation.deleted':
                return indexer.delete_accommodation(accommodation_id)
            
            else:
                print(f"⚠️ Unknown event type: {event_type}")
                return False

        except json.JSONDecodeError as e:
            print(f"❌ Error decoding message: {e}")
            return False
        except Exception as e:
            print(f"❌ Error processing message: {e}")
            return False

    def poll_messages(self):
        try:
            response = self.client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=settings.sqs_max_messages,
                WaitTimeSeconds=settings.sqs_poll_interval,
                VisibilityTimeout=settings.sqs_visibility_timeout,
                MessageAttributeNames=['All']
            )

            messages = response.get('Messages', [])
            
            if not messages:
                return 0

            processed_count = 0
            for message in messages:
                message_body = message['Body']
                receipt_handle = message['ReceiptHandle']
                
                if self.process_message(message_body):
                    self.client.delete_message(
                        QueueUrl=self.queue_url,
                        ReceiptHandle=receipt_handle
                    )
                    processed_count += 1
                else:
                    print(f"⚠️ Message processing failed, will retry")

            return processed_count

        except ClientError as e:
            print(f"❌ Error polling SQS: {e}")
            return 0
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return 0


consumer = SQSConsumer()
