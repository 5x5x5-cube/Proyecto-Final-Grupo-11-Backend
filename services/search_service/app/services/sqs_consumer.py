import json

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings
from app.services.redis_indexer import indexer

settings = get_settings()


class SQSConsumer:
    def __init__(self):
        client_kwargs = {
            "region_name": settings.aws_region,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
        }
        if settings.aws_endpoint_url:
            client_kwargs["endpoint_url"] = settings.aws_endpoint_url
        self.client = boto3.client("sqs", **client_kwargs)
        self.queue_url = settings.sqs_queue_url

    def process_message(self, message_body: str) -> bool:
        try:
            event = json.loads(message_body)
            event_type = event.get("event_type")
            entity_type = event.get("entity_type")
            data = event.get("data", {})

            if entity_type == "hotel":
                hotel = data.get("hotel", {})
                hotel_id = hotel.get("id")

                if not hotel_id:
                    print("No hotel ID in message")
                    return False

                if event_type == "created":
                    return indexer.index_hotel(hotel_id, hotel)
                elif event_type == "updated":
                    return indexer.update_hotel(hotel_id, hotel)
                elif event_type == "deleted":
                    return indexer.delete_hotel(hotel_id)

            elif entity_type == "room":
                room = data.get("room", {})
                room_id = room.get("id")

                if not room_id:
                    print("No room ID in message")
                    return False

                if event_type == "created":
                    return indexer.index_room(room_id, room)
                elif event_type == "updated":
                    return indexer.update_room(room_id, room)
                elif event_type == "deleted":
                    return indexer.delete_room(room_id)

            elif entity_type == "availability":
                availability = data.get("availability", {})
                room_id = availability.get("room_id")
                avail_date = availability.get("date")

                if not room_id or not avail_date:
                    print("No room_id or date in availability message")
                    return False

                if event_type in ("created", "updated"):
                    return indexer.index_availability(room_id, availability)
                elif event_type == "deleted":
                    return indexer.delete_availability(room_id, avail_date)

            else:
                print(f"Unknown entity type: {entity_type}")
                return False

        except json.JSONDecodeError as e:
            print(f"Error decoding message: {e}")
            return False
        except Exception as e:
            print(f"Error processing message: {e}")
            return False

    def poll_messages(self):
        try:
            response = self.client.receive_message(
                QueueUrl=self.queue_url,
                MaxNumberOfMessages=settings.sqs_max_messages,
                WaitTimeSeconds=settings.sqs_poll_interval,
                VisibilityTimeout=settings.sqs_visibility_timeout,
                MessageAttributeNames=["All"],
            )

            messages = response.get("Messages", [])

            if not messages:
                return 0

            processed_count = 0
            for message in messages:
                message_body = message["Body"]
                receipt_handle = message["ReceiptHandle"]

                if self.process_message(message_body):
                    self.client.delete_message(
                        QueueUrl=self.queue_url, ReceiptHandle=receipt_handle
                    )
                    processed_count += 1
                else:
                    print("Message processing failed, will retry")

            return processed_count

        except ClientError as e:
            print(f"Error polling SQS: {e}")
            return 0
        except Exception as e:
            print(f"Unexpected error: {e}")
            return 0


consumer = SQSConsumer()
