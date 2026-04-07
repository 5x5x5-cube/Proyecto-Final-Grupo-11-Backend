resource "aws_sqs_queue" "hotel_sync_dlq" {
  name                      = "${var.project_name}-${var.environment}-hotel-sync-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "${var.project_name}-${var.environment}-hotel-sync-dlq"
    Environment = var.environment
  }
}

resource "aws_sqs_queue" "hotel_sync" {
  name                       = "${var.project_name}-${var.environment}-hotel-sync-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.hotel_sync_dlq.arn
    maxReceiveCount     = 5
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-hotel-sync-queue"
    Environment = var.environment
  }
}

resource "aws_iam_policy" "sqs_access" {
  name        = "${var.project_name}-${var.environment}-sqs-access"
  description = "Policy for SQS access from EKS pods"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl",
          "sqs:ChangeMessageVisibility"
        ]
        Resource = [
          aws_sqs_queue.hotel_sync.arn,
          aws_sqs_queue.hotel_sync_dlq.arn
        ]
      }
    ]
  })

  tags = {
    Environment = var.environment
  }
}
