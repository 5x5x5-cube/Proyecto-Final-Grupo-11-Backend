terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "proyecto-final-terraform-state"
    key            = "eks/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "proyecto-final-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source = "./modules/vpc"
  
  project_name = var.project_name
  environment  = var.environment
  vpc_cidr     = var.vpc_cidr
  azs          = var.availability_zones
}

module "eks" {
  source = "./modules/eks"
  
  project_name        = var.project_name
  environment         = var.environment
  aws_region          = var.aws_region
  cluster_version     = var.cluster_version
  vpc_id              = module.vpc.vpc_id
  private_subnet_ids  = module.vpc.private_subnet_ids
  node_instance_types = var.node_instance_types
  node_desired_size   = var.node_desired_size
  node_min_size       = var.node_min_size
  node_max_size       = var.node_max_size
}

module "ecr" {
  source = "./modules/ecr"
  
  project_name = var.project_name
  environment  = var.environment
  repositories = var.ecr_repositories
}

module "rds" {
  source = "./modules/rds"
  
  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  db_instance_class  = var.db_instance_class
  db_name            = var.db_name
  db_username        = var.db_username
}

module "elasticache" {
  source = "./modules/elasticache"
  
  project_name       = var.project_name
  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  node_type          = var.redis_node_type
  num_cache_nodes    = var.redis_num_cache_nodes
}

module "sqs" {
  source = "./modules/sqs"
  
  project_name = var.project_name
  environment  = var.environment
}

module "irsa" {
  source = "./modules/irsa"

  project_name           = var.project_name
  environment            = var.environment
  eks_oidc_issuer_url    = module.eks.oidc_issuer_url
  eks_oidc_provider_arn  = module.eks.oidc_provider_arn
  sqs_access_policy_arn  = module.sqs.sqs_access_policy_arn
}

module "alb_controller" {
  source = "./modules/alb-controller"

  project_name          = var.project_name
  environment           = var.environment
  eks_cluster_name      = module.eks.cluster_name
  eks_oidc_issuer_url  = module.eks.oidc_issuer_url
  eks_oidc_provider_arn = module.eks.oidc_provider_arn
  vpc_id                = module.vpc.vpc_id
}
