#!/usr/bin/env python3
"""
SQS Worker for Booking Service
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings  # noqa: E402
from app.services.sqs_consumer import consumer  # noqa: E402

settings = get_settings()


async def process_messages(messages):
    processed = 0
    for message in messages:
        message_body = message["Body"]
        receipt_handle = message["ReceiptHandle"]

        success = await consumer.process_message(message_body)
        if success:
            consumer.delete_message(receipt_handle)
            processed += 1
        else:
            print("Message processing failed, will retry")
    return processed


def main():
    print("Starting SQS Worker for Booking Service...")
    print(f"Polling queue: {settings.sqs_queue_url}")
    print(f"Poll interval: {settings.sqs_poll_interval} seconds")
    print("-" * 60)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    while True:
        try:
            count, messages = consumer.poll_messages()

            if count > 0:
                processed = loop.run_until_complete(process_messages(messages))
                print(f"Processed {processed} message(s)")
            else:
                print("No messages, waiting...")

            time.sleep(1)

        except KeyboardInterrupt:
            print("\nShutting down worker...")
            break
        except Exception as e:
            print(f"Worker error: {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

    loop.close()


if __name__ == "__main__":
    main()
