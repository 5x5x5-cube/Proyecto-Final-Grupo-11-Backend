output "hotel_sync_queue_url" {
  description = "Hotel sync SQS queue URL"
  value       = aws_sqs_queue.hotel_sync.url
}

output "hotel_sync_queue_arn" {
  description = "Hotel sync SQS queue ARN"
  value       = aws_sqs_queue.hotel_sync.arn
}

output "hotel_sync_dlq_url" {
  description = "Hotel sync DLQ URL"
  value       = aws_sqs_queue.hotel_sync_dlq.url
}

output "sqs_access_policy_arn" {
  description = "SQS access IAM policy ARN"
  value       = aws_iam_policy.sqs_access.arn
}
