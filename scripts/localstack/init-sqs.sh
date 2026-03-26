#!/bin/bash

echo "🚀 Initializing LocalStack SQS..."

# Wait for LocalStack to be ready
sleep 5

# Create SQS queue
awslocal sqs create-queue \
    --queue-name accommodation-sync-queue \
    --attributes VisibilityTimeout=300,MessageRetentionPeriod=1209600

# Create Dead Letter Queue
awslocal sqs create-queue \
    --queue-name accommodation-sync-dlq \
    --attributes MessageRetentionPeriod=1209600

echo "✅ SQS queues created successfully"

# List queues
echo "📋 Available queues:"
awslocal sqs list-queues
