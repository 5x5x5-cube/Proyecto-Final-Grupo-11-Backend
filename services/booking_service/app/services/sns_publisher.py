import json
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from ..config import settings


class SNSPublisher:
    def __init__(self):
        client_kwargs = {
            "region_name": settings.aws_region,
        }
        if settings.aws_access_key_id and settings.aws_access_key_id != "test":
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url

        self.client = boto3.client("sns", **client_kwargs)
        self.topic_arn = settings.sns_topic_arn

    async def publish_event(
        self,
        event_type: str,
        entity_type: str,
        entity_data: Dict[str, Any],
        previous_state: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "entity_type": entity_type,
                "timestamp": datetime.utcnow().isoformat(),
                "data": {entity_type: entity_data, "previous_state": previous_state},
                "metadata": {
                    "retry_count": 0,
                    "correlation_id": str(uuid.uuid4()),
                    "source_service": "booking-service",
                },
            }

            response = self.client.publish(
                TopicArn=self.topic_arn,
                Message=json.dumps(event, default=str),
                MessageAttributes={
                    "event_type": {"StringValue": event_type, "DataType": "String"},
                    "entity_type": {"StringValue": entity_type, "DataType": "String"},
                },
            )

            print(f"Event published to SNS: {event_type} - MessageId: {response['MessageId']}")
            return True

        except ClientError as e:
            print(f"Error publishing to SNS: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error: {e}")
            return False

    async def publish_booking_status_updated(
        self,
        booking_id: str,
        user_id: str,
        hotel_id: str,
        status: str,
        hotel_name: str,
        check_in: str,
        check_out: str,
    ) -> bool:
        return await self.publish_event(
            event_type="booking_status_updated",
            entity_type="booking",
            entity_data={
                "id": booking_id,
                "user_id": user_id,
                "hotel_id": hotel_id,
                "status": status,
                "hotel_name": hotel_name,
                "check_in": check_in,
                "check_out": check_out,
            },
        )


sns_publisher = SNSPublisher()
