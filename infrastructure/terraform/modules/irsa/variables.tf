variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Environment"
  type        = string
}

variable "eks_oidc_issuer_url" {
  description = "EKS OIDC issuer URL"
  type        = string
}

variable "eks_oidc_provider_arn" {
  description = "EKS OIDC provider ARN"
  type        = string
}

variable "sqs_access_policy_arn" {
  description = "ARN of the SQS access IAM policy"
  type        = string
}

variable "sns_publish_policy_arn" {
  description = "ARN of the SNS publish IAM policy"
  type        = string
}

variable "payment_booking_sqs_access_policy_arn" {
  description = "ARN of the payment-booking SQS access IAM policy"
  type        = string
}
