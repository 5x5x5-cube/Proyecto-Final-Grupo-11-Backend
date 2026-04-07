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

variable "sqs_access_policy_arn" {
  description = "ARN of the SQS access IAM policy"
  type        = string
}
