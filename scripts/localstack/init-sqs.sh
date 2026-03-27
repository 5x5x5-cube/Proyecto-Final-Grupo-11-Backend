#!/bin/bash

echo "Initializing LocalStack SQS..."

sleep 5

awslocal sqs create-queue \
    --queue-name hotel-sync-queue \
    --attributes VisibilityTimeout=300,MessageRetentionPeriod=1209600

awslocal sqs create-queue \
    --queue-name hotel-sync-dlq \
    --attributes MessageRetentionPeriod=1209600

echo "SQS queues created successfully"

echo "Available queues:"
awslocal sqs list-queues
