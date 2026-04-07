data "aws_iam_openid_connect_provider" "eks" {
  url = var.eks_oidc_issuer_url
}

resource "aws_iam_role" "inventory_service" {
  name = "${var.project_name}-${var.environment}-inventory-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.eks.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(var.eks_oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:default:inventory-service-sa"
          "${replace(var.eks_oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Environment = var.environment
    Service     = "inventory-service"
  }
}

resource "aws_iam_role_policy_attachment" "inventory_sqs" {
  role       = aws_iam_role.inventory_service.name
  policy_arn = var.sqs_access_policy_arn
}

resource "aws_iam_role" "search_service" {
  name = "${var.project_name}-${var.environment}-search-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Federated = data.aws_iam_openid_connect_provider.eks.arn
      }
      Action = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${replace(var.eks_oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:default:search-service-sa"
          "${replace(var.eks_oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
        }
      }
    }]
  })

  tags = {
    Environment = var.environment
    Service     = "search-service"
  }
}

resource "aws_iam_role_policy_attachment" "search_sqs" {
  role       = aws_iam_role.search_service.name
  policy_arn = var.sqs_access_policy_arn
}
