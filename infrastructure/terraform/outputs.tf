output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "eks_cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "eks_cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "eks_cluster_certificate_authority_data" {
  description = "EKS cluster certificate authority data"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "ecr_repository_urls" {
  description = "ECR repository URLs"
  value       = module.ecr.repository_urls
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.db_endpoint
}

output "rds_database_name" {
  description = "RDS database name"
  value       = module.rds.db_name
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = module.elasticache.redis_endpoint
}

output "sqs_hotel_sync_queue_url" {
  description = "SQS hotel sync queue URL"
  value       = module.sqs.hotel_sync_queue_url
}

output "sqs_hotel_sync_dlq_url" {
  description = "SQS hotel sync DLQ URL"
  value       = module.sqs.hotel_sync_dlq_url
}

output "inventory_service_role_arn" {
  description = "IAM role ARN for inventory-service IRSA"
  value       = module.irsa.inventory_service_role_arn
}

output "search_service_role_arn" {
  description = "IAM role ARN for search-service IRSA"
  value       = module.irsa.search_service_role_arn
}

output "payment_service_role_arn" {
  description = "IAM role ARN for payment-service IRSA"
  value       = module.irsa.payment_service_role_arn
}

output "booking_service_role_arn" {
  description = "IAM role ARN for booking-service IRSA"
  value       = module.irsa.booking_service_role_arn
}

output "sns_topic_arn" {
  description = "ARN of the command-update SNS topic"
  value       = module.sns.sns_topic_arn
}

output "sns_payment_booking_queue_url" {
  description = "Payment-booking SQS queue URL"
  value       = module.sns.payment_booking_queue_url
}

output "sns_notification_queue_url" {
  description = "Notification SQS queue URL"
  value       = module.sns.notification_queue_url
}
