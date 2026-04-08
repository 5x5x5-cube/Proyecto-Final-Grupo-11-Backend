aws_region = "us-east-1"
project_name = "proyecto-final"
environment = "dev"

vpc_cidr = "10.0.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]

cluster_version = "1.27"
node_instance_types = ["t3.small"]
node_desired_size = 1
node_min_size = 1
node_max_size = 2

ecr_repositories = [
  "auth-service",
  "booking-service",
  "search-service",
  "cart-service",
  "reports-service",
  "inventory-service",
  "commercial-service",
  "notification-service",
  "payment-service",
  "health-copilot"
]

redis_node_type = "cache.t3.micro"
redis_num_cache_nodes = 1

db_instance_class = "db.t3.micro"
db_name = "proyectofinal"
db_username = "admin"
