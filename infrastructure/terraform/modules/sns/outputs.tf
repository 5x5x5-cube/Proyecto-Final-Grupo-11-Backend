output "sns_topic_arn" {
  description = "ARN of the command-update SNS topic"
  value       = aws_sns_topic.command_update.arn
}

output "sns_publish_policy_arn" {
  description = "ARN of the SNS publish IAM policy"
  value       = aws_iam_policy.sns_publish_access.arn
}

output "payment_booking_queue_url" {
  description = "Payment-booking SQS queue URL"
  value       = aws_sqs_queue.payment_booking.url
}

output "payment_booking_queue_arn" {
  description = "Payment-booking SQS queue ARN"
  value       = aws_sqs_queue.payment_booking.arn
}

output "payment_booking_sqs_access_policy_arn" {
  description = "ARN of the payment-booking SQS access IAM policy"
  value       = aws_iam_policy.payment_booking_sqs_access.arn
}

output "notification_queue_url" {
  description = "Notification SQS queue URL"
  value       = aws_sqs_queue.notification.url
}

output "notification_queue_arn" {
  description = "Notification SQS queue ARN"
  value       = aws_sqs_queue.notification.arn
}
