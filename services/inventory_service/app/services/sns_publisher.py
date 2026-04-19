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
                    "source_service": "inventory-service",
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

    async def publish_hotel_created(self, hotel_data: Dict[str, Any]) -> bool:
        return await self.publish_event("created", "hotel", hotel_data)

    async def publish_hotel_updated(
        self, hotel_data: Dict[str, Any], previous_state: Dict[str, Any]
    ) -> bool:
        return await self.publish_event("updated", "hotel", hotel_data, previous_state)

    async def publish_hotel_deleted(self, hotel_data: Dict[str, Any]) -> bool:
        return await self.publish_event("deleted", "hotel", hotel_data)

    async def publish_room_created(self, room_data: Dict[str, Any]) -> bool:
        return await self.publish_event("created", "room", room_data)

    async def publish_room_updated(
        self, room_data: Dict[str, Any], previous_state: Dict[str, Any]
    ) -> bool:
        return await self.publish_event("updated", "room", room_data, previous_state)

    async def publish_room_deleted(self, room_data: Dict[str, Any]) -> bool:
        return await self.publish_event("deleted", "room", room_data)

    async def publish_availability_created(self, availability_data: Dict[str, Any]) -> bool:
        return await self.publish_event("created", "availability", availability_data)

    async def publish_availability_updated(self, availability_data: Dict[str, Any]) -> bool:
        return await self.publish_event("updated", "availability", availability_data)

    async def publish_tariff_upserted(self, tariff_data: Dict[str, Any], is_update: bool = False) -> bool:
        event_type = "updated" if is_update else "created"
        return await self.publish_event(event_type, "tariff", tariff_data)

    async def publish_tariff_deleted(self, tariff_data: Dict[str, Any]) -> bool:
        return await self.publish_event("deleted", "tariff", tariff_data)


sns_publisher = SNSPublisher()
