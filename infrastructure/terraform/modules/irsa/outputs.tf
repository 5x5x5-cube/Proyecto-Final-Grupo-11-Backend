output "inventory_service_role_arn" {
  description = "IAM role ARN for inventory-service"
  value       = aws_iam_role.inventory_service.arn
}

output "search_service_role_arn" {
  description = "IAM role ARN for search-service"
  value       = aws_iam_role.search_service.arn
}
