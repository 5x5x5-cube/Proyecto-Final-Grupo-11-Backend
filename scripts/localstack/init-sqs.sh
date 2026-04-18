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

# Create SNS topic
awslocal sns create-topic --name command-update --region us-east-1

# Create new SQS queues
awslocal sqs create-queue --queue-name payment-booking-dlq --region us-east-1
awslocal sqs create-queue --queue-name payment-booking-queue --region us-east-1 \
  --attributes '{"VisibilityTimeout":"300","RedrivePolicy":"{\"deadLetterTargetArn\":\"arn:aws:sqs:us-east-1:000000000000:payment-booking-dlq\",\"maxReceiveCount\":\"5\"}"}'

awslocal sqs create-queue --queue-name notification-dlq --region us-east-1
awslocal sqs create-queue --queue-name notification-queue --region us-east-1 \
  --attributes '{"VisibilityTimeout":"300","RedrivePolicy":"{\"deadLetterTargetArn\":\"arn:aws:sqs:us-east-1:000000000000:notification-dlq\",\"maxReceiveCount\":\"5\"}"}'

# Subscribe queues to SNS with filters
TOPIC_ARN="arn:aws:sns:us-east-1:000000000000:command-update"

awslocal sns subscribe --topic-arn $TOPIC_ARN --protocol sqs \
  --notification-endpoint arn:aws:sqs:us-east-1:000000000000:hotel-sync-queue \
  --attributes '{"FilterPolicy":"{\"entity_type\":[\"hotel\",\"room\",\"availability\"]}","RawMessageDelivery":"true"}'

awslocal sns subscribe --topic-arn $TOPIC_ARN --protocol sqs \
  --notification-endpoint arn:aws:sqs:us-east-1:000000000000:payment-booking-queue \
  --attributes '{"FilterPolicy":"{\"event_type\":[\"payment_confirmed\"]}","RawMessageDelivery":"true"}'

awslocal sns subscribe --topic-arn $TOPIC_ARN --protocol sqs \
  --notification-endpoint arn:aws:sqs:us-east-1:000000000000:notification-queue \
  --attributes '{"FilterPolicy":"{\"entity_type\":[\"payment\"]}","RawMessageDelivery":"true"}'
