import json
import uuid
from datetime import datetime
from typing import Dict, Any
import boto3
from botocore.exceptions import ClientError
from app.config import get_settings

settings = get_settings()


class SQSPublisher:
    def __init__(self):
        self.client = boto3.client(
            'sqs',
            region_name=settings.aws_region,
            endpoint_url=settings.aws_endpoint_url,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.queue_url = settings.sqs_queue_url

    async def publish_event(
        self,
        event_type: str,
        accommodation_data: Dict[str, Any],
        previous_state: Dict[str, Any] | None = None
    ) -> bool:
        try:
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": {
                    "accommodation": accommodation_data,
                    "previous_state": previous_state
                },
                "metadata": {
                    "retry_count": 0,
                    "correlation_id": str(uuid.uuid4()),
                    "source_service": "inventory-service"
                }
            }

            response = self.client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(event, default=str),
                MessageAttributes={
                    'event_type': {
                        'StringValue': event_type,
                        'DataType': 'String'
                    }
                }
            )

            print(f"✅ Event published to SQS: {event_type} - MessageId: {response['MessageId']}")
            return True

        except ClientError as e:
            print(f"❌ Error publishing to SQS: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False

    async def publish_accommodation_created(self, accommodation_data: Dict[str, Any]) -> bool:
        return await self.publish_event("accommodation.created", accommodation_data)

    async def publish_accommodation_updated(
        self,
        accommodation_data: Dict[str, Any],
        previous_state: Dict[str, Any]
    ) -> bool:
        return await self.publish_event(
            "accommodation.updated",
            accommodation_data,
            previous_state
        )

    async def publish_accommodation_deleted(self, accommodation_data: Dict[str, Any]) -> bool:
        return await self.publish_event("accommodation.deleted", accommodation_data)


sqs_publisher = SQSPublisher()
