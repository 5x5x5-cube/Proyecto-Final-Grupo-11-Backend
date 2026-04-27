# Infrastructure Guide — Deploy & Destroy

## Prerequisites

- AWS CLI configured with profile `maestria` (`~/.aws/credentials`)
- `terraform`, `kubectl`, `docker` installed
- AWS region: `us-east-1`

---

## 🟢 Deploy (from scratch, ~30 min)

### 1. Provision infrastructure (~15-20 min)

```bash
export AWS_PROFILE=maestria
cd infrastructure/terraform
terraform init
terraform apply
```

This creates: VPC, EKS cluster, RDS (PostgreSQL), ElastiCache (Redis), SNS topic (CommandUpdate EventBus), SQS queues (hotel-sync, payment-booking, notification), ECR repos, IAM roles.

### 2. Configure kubectl

```bash
aws eks update-kubeconfig --name proyecto-final-dev --region us-east-1
```

### 3. Create K8s secrets and ConfigMaps (~2 min)

```bash
cd ../..
bash scripts/setup-k8s.sh
```

### 4. Build and push Docker images (~5 min)

```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 618246140762.dkr.ecr.us-east-1.amazonaws.com

for service in auth-service booking-service cart-service inventory-service search-service; do
  docker buildx build --platform linux/amd64 \
    -t 618246140762.dkr.ecr.us-east-1.amazonaws.com/proyecto-final-dev-${service}:latest \
    services/${service//-/_} --push
done
```

### 5. Deploy K8s resources (~2 min)

```bash
kubectl apply -f kubernetes/deployments/auth-service.yaml
kubectl apply -f kubernetes/deployments/booking-service.yaml
kubectl apply -f kubernetes/deployments/cart-service.yaml
kubectl apply -f kubernetes/deployments/inventory-service.yaml
kubectl apply -f kubernetes/deployments/search-service.yaml
kubectl apply -f kubernetes/deployments/search-worker.yaml
kubectl apply -f kubernetes/ingress.yaml
```

Scale down unused services to stay within pod limits (11 max on t3.small):

```bash
kubectl scale deployment notification-service commercial-service payment-service reports-service --replicas=0 2>/dev/null
```

### 6. Seed data (~2 min)

```bash
# Seed hotels/rooms/availability into PostgreSQL
kubectl exec deployment/inventory-service -- python -m scripts.seed

# Publish to SQS for search service indexing (hotels)
QUEUE_URL=$(aws sqs get-queue-url --queue-name proyecto-final-dev-hotel-sync-queue --query QueueUrl --output text)

# Hotels
for hotel in \
  '{"event_type":"created","entity_type":"hotel","data":{"hotel":{"id":"a1000000-0000-0000-0000-000000000001","name":"Hotel Caribe Plaza","description":"Luxury beachfront hotel in Cartagena","city":"Cartagena","country":"Colombia","rating":4.5}}}' \
  '{"event_type":"created","entity_type":"hotel","data":{"hotel":{"id":"a1000000-0000-0000-0000-000000000002","name":"Bogota Grand Hotel","description":"Modern business hotel in Bogota","city":"Bogota","country":"Colombia","rating":4.2}}}' \
  '{"event_type":"created","entity_type":"hotel","data":{"hotel":{"id":"a1000000-0000-0000-0000-000000000003","name":"Medellin Eco Resort","description":"Eco-friendly resort in Medellin","city":"Medellin","country":"Colombia","rating":4.7}}}'; do
  aws sqs send-message --queue-url "$QUEUE_URL" --message-body "$hotel" --region us-east-1 > /dev/null
done

# Rooms (repeat for each room — see scripts/seed.py for full list)
# The search-worker pod will automatically consume SQS messages and index into Redis.
```

### 7. Deploy frontend (~1 min)

```bash
cd /path/to/travelhub-prototype
echo "VITE_API_BASE_URL=https://<ELB_URL>/api/v1" > .env
npm run build
aws s3 sync dist/ s3://proyecto-final-dev-frontend/ --delete
aws cloudfront create-invalidation --distribution-id EQMVV4VG9E7CP --paths "/*"
```

### 8. Verify

```bash
# Check pods
kubectl get pods

# Test endpoints
curl -sk https://<ELB_URL>/api/v1/search/hotels/a1000000-0000-0000-0000-000000000001
curl -sk https://<ELB_URL>/api/v1/bookings/hotel
curl -sk https://<ELB_URL>/api/v1/cart -H "X-User-Id: c1000000-0000-0000-0000-000000000001"
```

---

## 🔴 Destroy (~15 min)

### 1. Scale down all deployments

```bash
export AWS_PROFILE=maestria
aws eks update-kubeconfig --name proyecto-final-dev --region us-east-1
kubectl scale deployment --all --replicas=0 -n default
```

### 2. Delete K8s resources (CRITICAL — prevents terraform from hanging)

The NGINX ingress controller creates AWS Load Balancers outside of Terraform. These must be deleted **before** `terraform destroy`, otherwise subnets and the internet gateway will hang for 20+ min and fail with `DependencyViolation`.

```bash
# Delete all ingresses (this triggers ELB cleanup)
kubectl delete ingress --all

# Delete all services and deployments
kubectl delete svc --all -l app
kubectl delete deployment --all
kubectl delete configmap shared-infra-config shared-service-discovery 2>/dev/null

# Wait ~60s for AWS to release the ELB network interfaces
sleep 60

# Verify no load balancers remain in the VPC
aws elbv2 describe-load-balancers --region us-east-1 --query 'LoadBalancers[*].{Name:LoadBalancerName,VPC:VpcId}'
# Should return [] — if not, delete them manually:
# aws elbv2 delete-load-balancer --load-balancer-arn <ARN> --region us-east-1
```

### 3. Terraform destroy

```bash
cd infrastructure/terraform
terraform init   # if not already initialized
terraform destroy -auto-approve
```

This takes ~10-15 min (EKS node group and NAT gateway are slowest).

### 4. If terraform destroy fails on VPC resources

This happens when ELB network interfaces weren't fully released. Fix:

```bash
# Find orphaned load balancers
aws elbv2 describe-load-balancers --region us-east-1

# Delete them
aws elbv2 delete-load-balancer --load-balancer-arn <ARN> --region us-east-1

# Wait for ENIs to be released
sleep 60
aws ec2 describe-network-interfaces --filters "Name=vpc-id,Values=<VPC_ID>" --region us-east-1

# Retry destroy
terraform destroy -auto-approve
```

### 5. Clean up kubeconfig

```bash
kubectl config delete-context arn:aws:eks:us-east-1:618246140762:cluster/proyecto-final-dev 2>/dev/null
```

---

## 💰 Cost reference (per month, running 24/7)

| Resource | Type | Cost/month |
|----------|------|------------|
| EKS Control Plane | — | $73 |
| NAT Gateway | 1x | $32 + data |
| EC2 Node | t3.small x1 | $15 |
| RDS | db.t3.micro | $15 |
| ElastiCache | cache.t3.micro | $13 |
| ECR | 10 repos | ~$1 |
| SNS + SQS | 1 topic, 3 queues | ~$0 |
| CloudFront + S3 | Frontend | ~$1 |
| **Total** | | **~$150/month (~$5/day)** |

**Tip:** If you only need to pause temporarily, scaling pods to 0 saves EC2 compute but EKS ($73) and NAT Gateway ($32) still charge. Full `terraform destroy` is the only way to stop all costs.

---

## ⚠️ Notes

- **ECR images are destroyed** — you'll need to rebuild and push Docker images after recreating
- **RDS data is lost** — the seed script recreates hotels/rooms/availability
- **Redis data is lost** — the search-worker re-indexes from SQS messages
- **ELB URL changes** — update the frontend `.env` and mobile `.env` with the new URL after redeploy
- **Frontend (CloudFront/S3)** is managed by separate Terraform in `travelhub-prototype/infrastructure/terraform/` — not destroyed here
- **Pod limit** — t3.small supports max 11 pods (4 are system). Keep 6-7 app pods max
