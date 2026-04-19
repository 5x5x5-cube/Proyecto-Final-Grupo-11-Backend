# SNS Topic
resource "aws_sns_topic" "command_update" {
  name = "${var.project_name}-${var.environment}-command-update"

  tags = {
    Name        = "${var.project_name}-${var.environment}-command-update"
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Payment-Booking queue + DLQ
# ---------------------------------------------------------------------------
resource "aws_sqs_queue" "payment_booking_dlq" {
  name                      = "${var.project_name}-${var.environment}-payment-booking-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "${var.project_name}-${var.environment}-payment-booking-dlq"
    Environment = var.environment
  }
}

resource "aws_sqs_queue" "payment_booking" {
  name                       = "${var.project_name}-${var.environment}-payment-booking-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.payment_booking_dlq.arn
    maxReceiveCount     = 5
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-payment-booking-queue"
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# Notification queue + DLQ
# ---------------------------------------------------------------------------
resource "aws_sqs_queue" "notification_dlq" {
  name                      = "${var.project_name}-${var.environment}-notification-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "${var.project_name}-${var.environment}-notification-dlq"
    Environment = var.environment
  }
}

resource "aws_sqs_queue" "notification" {
  name                       = "${var.project_name}-${var.environment}-notification-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 345600 # 4 days
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notification_dlq.arn
    maxReceiveCount     = 5
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-notification-queue"
    Environment = var.environment
  }
}

# ---------------------------------------------------------------------------
# SNS -> SQS subscriptions
# ---------------------------------------------------------------------------
resource "aws_sns_topic_subscription" "hotel_sync" {
  topic_arn            = aws_sns_topic.command_update.arn
  protocol             = "sqs"
  endpoint             = var.hotel_sync_queue_arn
  raw_message_delivery = true

  filter_policy = jsonencode({
    entity_type = ["hotel", "room", "availability"]
  })

  filter_policy_scope = "MessageAttributes"
}

resource "aws_sns_topic_subscription" "payment_booking" {
  topic_arn            = aws_sns_topic.command_update.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.payment_booking.arn
  raw_message_delivery = true

  filter_policy = jsonencode({
    event_type = ["payment_confirmed"]
  })

  filter_policy_scope = "MessageAttributes"
}

resource "aws_sns_topic_subscription" "notification" {
  topic_arn            = aws_sns_topic.command_update.arn
  protocol             = "sqs"
  endpoint             = aws_sqs_queue.notification.arn
  raw_message_delivery = true

  filter_policy = jsonencode({
    entity_type = ["payment", "booking"]
  })

  filter_policy_scope = "MessageAttributes"
}

# ---------------------------------------------------------------------------
# SQS queue policies — allow SNS to send messages
# ---------------------------------------------------------------------------
resource "aws_sqs_queue_policy" "hotel_sync" {
  queue_url = var.hotel_sync_queue_url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSNSPublish"
        Effect = "Allow"
        Principal = {
          Service = "sns.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = var.hotel_sync_queue_arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_sns_topic.command_update.arn
          }
        }
      }
    ]
  })
}

resource "aws_sqs_queue_policy" "payment_booking" {
  queue_url = aws_sqs_queue.payment_booking.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSNSPublish"
        Effect = "Allow"
        Principal = {
          Service = "sns.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.payment_booking.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_sns_topic.command_update.arn
          }
        }
      }
    ]
  })
}

resource "aws_sqs_queue_policy" "notification" {
  queue_url = aws_sqs_queue.notification.url

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowSNSPublish"
        Effect = "Allow"
        Principal = {
          Service = "sns.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.notification.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_sns_topic.command_update.arn
          }
        }
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# IAM policies
# ---------------------------------------------------------------------------
resource "aws_iam_policy" "sns_publish_access" {
  name        = "${var.project_name}-${var.environment}-sns-publish-access"
  description = "Policy to allow publishing to the command-update SNS topic"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "sns:Publish"
        Resource = aws_sns_topic.command_update.arn
      }
    ]
  })

  tags = {
    Environment = var.environment
  }
}

resource "aws_iam_policy" "payment_booking_sqs_access" {
  name        = "${var.project_name}-${var.environment}-payment-booking-sqs-access"
  description = "Policy for SQS access to payment-booking queue from EKS pods"

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
          aws_sqs_queue.payment_booking.arn,
          aws_sqs_queue.payment_booking_dlq.arn
        ]
      }
    ]
  })

  tags = {
    Environment = var.environment
  }
}
