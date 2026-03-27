#!/usr/bin/env python3
"""
SQS Worker for Search Service
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.config import get_settings
from app.services.sqs_consumer import consumer

settings = get_settings()


def main():
    print("Starting SQS Worker for Search Service...")
    print(f"Polling queue: {settings.sqs_queue_url}")
    print(f"Poll interval: {settings.sqs_poll_interval} seconds")
    print("-" * 60)

    while True:
        try:
            processed = consumer.poll_messages()

            if processed > 0:
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


if __name__ == "__main__":
    main()
