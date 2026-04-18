variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "hotel_sync_queue_arn" {
  description = "ARN of the hotel sync SQS queue (from SQS module)"
  type        = string
}

variable "hotel_sync_queue_url" {
  description = "URL of the hotel sync SQS queue (from SQS module)"
  type        = string
}
