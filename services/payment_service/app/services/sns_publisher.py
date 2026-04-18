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
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
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
                    "source_service": "payment-service",
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

    async def publish_payment_confirmed(self, payment_data: Dict[str, Any]) -> bool:
        return await self.publish_event("payment_confirmed", "payment", payment_data)

    async def publish_payment_declined(self, payment_data: Dict[str, Any]) -> bool:
        return await self.publish_event("payment_declined", "payment", payment_data)


sns_publisher = SNSPublisher()
