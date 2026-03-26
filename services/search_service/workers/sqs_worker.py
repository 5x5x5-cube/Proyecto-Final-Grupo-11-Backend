#!/usr/bin/env python3
"""
SQS Worker for Search Service

This worker continuously polls the SQS queue for accommodation events
and indexes them in Redis for fast searching.

Usage:
    python workers/sqs_worker.py
"""

import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from app.services.sqs_consumer import consumer
from app.config import get_settings

settings = get_settings()


def main():
    print("🚀 Starting SQS Worker for Search Service...")
    print(f"📬 Polling queue: {settings.sqs_queue_url}")
    print(f"⏱️  Poll interval: {settings.sqs_poll_interval} seconds")
    print(f"📊 Max messages per poll: {settings.sqs_max_messages}")
    print("-" * 60)
    
    while True:
        try:
            processed = consumer.poll_messages()
            
            if processed > 0:
                print(f"✅ Processed {processed} message(s)")
            else:
                print("⏳ No messages, waiting...")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n👋 Shutting down worker...")
            break
        except Exception as e:
            print(f"❌ Worker error: {e}")
            print("⏳ Retrying in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    main()
