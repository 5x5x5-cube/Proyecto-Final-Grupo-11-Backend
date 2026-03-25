# Guía de Despliegue

Esta guía te ayudará a desplegar el proyecto completo en AWS EKS.

## Prerrequisitos

1. **AWS CLI** instalado y configurado
2. **kubectl** instalado
3. **Terraform** >= 1.0 instalado
4. **Docker** instalado
5. **Cuenta de AWS** con permisos para crear:
   - VPC, Subnets, Internet Gateway, NAT Gateway
   - EKS Cluster
   - ECR Repositories
   - RDS Instances
   - IAM Roles y Policies

## Paso 1: Configurar AWS CLI

```bash
aws configure
# Ingresa:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: us-east-1
# - Default output format: json
```

## Paso 2: Crear Backend de Terraform

```bash
# Crear bucket S3 para Terraform state
aws s3 mb s3://proyecto-final-terraform-state --region us-east-1

# Habilitar versionado
aws s3api put-bucket-versioning \
  --bucket proyecto-final-terraform-state \
  --versioning-configuration Status=Enabled

# Crear tabla DynamoDB para locks
aws dynamodb create-table \
  --table-name proyecto-final-terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

## Paso 3: Desplegar Infraestructura con Terraform

```bash
cd infrastructure/terraform

# Inicializar Terraform
terraform init

# Validar configuración
terraform validate

# Ver plan de ejecución
terraform plan -var-file=terraform.tfvars

# Aplicar cambios (esto tomará ~15-20 minutos)
terraform apply -var-file=terraform.tfvars

# Guardar outputs importantes
terraform output > outputs.txt
```

## Paso 4: Configurar kubectl

```bash
# Actualizar kubeconfig
aws eks update-kubeconfig --name proyecto-final-dev --region us-east-1

# Verificar conexión
kubectl get nodes
kubectl get namespaces
```

## Paso 5: Instalar AWS Load Balancer Controller

```bash
# Descargar policy IAM
curl -o iam_policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.6.0/docs/install/iam_policy.json

# Crear policy
aws iam create-policy \
    --policy-name AWSLoadBalancerControllerIAMPolicy \
    --policy-document file://iam_policy.json

# Crear service account
eksctl create iamserviceaccount \
  --cluster=proyecto-final-dev \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --attach-policy-arn=arn:aws:iam::<ACCOUNT_ID>:policy/AWSLoadBalancerControllerIAMPolicy \
  --override-existing-serviceaccounts \
  --approve

# Instalar con Helm
helm repo add eks https://aws.github.io/eks-charts
helm repo update

helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=proyecto-final-dev \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller
```

## Paso 6: Construir y Subir Imágenes Docker

```bash
# Obtener URL del registry ECR
ECR_REGISTRY=$(aws ecr describe-repositories --repository-names proyecto-final-dev-auth-service --query 'repositories[0].repositoryUri' --output text | cut -d'/' -f1)

# Login a ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REGISTRY

# Script para construir y subir todos los servicios
for service in auth_service booking_service search_service cart_service reports_service inventory_service commercial_service notification_service payment_service health_copilot; do
  SERVICE_NAME=$(echo $service | sed 's/_/-/g')
  echo "Building and pushing $SERVICE_NAME..."
  
  cd services/$service
  docker build -t $ECR_REGISTRY/proyecto-final-dev-$SERVICE_NAME:latest .
  docker push $ECR_REGISTRY/proyecto-final-dev-$SERVICE_NAME:latest
  cd ../..
done
```

## Paso 7: Actualizar Manifests de Kubernetes

```bash
# Reemplazar variables en los manifests
ECR_REGISTRY=$(aws ecr describe-repositories --repository-names proyecto-final-dev-auth-service --query 'repositories[0].repositoryUri' --output text | cut -d'/' -f1)

for file in kubernetes/deployments/*.yaml; do
  sed -i "s|\${ECR_REGISTRY}|$ECR_REGISTRY/proyecto-final-dev|g" $file
  sed -i "s|\${IMAGE_TAG}|latest|g" $file
done
```

## Paso 8: Crear Secrets de Kubernetes

```bash
# Obtener password de RDS desde Secrets Manager
DB_PASSWORD=$(aws secretsmanager get-secret-value --secret-id proyecto-final-dev-db-password --query SecretString --output text)

# Obtener endpoint de RDS
DB_ENDPOINT=$(terraform output -raw rds_endpoint)

# Crear secrets para cada servicio que use base de datos
for service in auth-service booking-service reports-service inventory-service commercial-service payment-service; do
  kubectl create secret generic ${service}-secrets \
    --from-literal=database-url="postgresql://admin:${DB_PASSWORD}@${DB_ENDPOINT}/proyectofinal"
done

# Crear configmaps para servicios que usen Redis
# Primero, desplegar Redis en el cluster o usar ElastiCache
kubectl create configmap cart-service-config --from-literal=redis-url="redis://redis:6379"
kubectl create configmap notification-service-config --from-literal=redis-url="redis://redis:6379"
```

## Paso 9: Desplegar Servicios en Kubernetes

```bash
# Aplicar todos los deployments
kubectl apply -f kubernetes/deployments/

# Aplicar ingress
kubectl apply -f kubernetes/ingress.yaml

# Verificar deployments
kubectl get deployments
kubectl get pods
kubectl get services
kubectl get ingress
```

## Paso 10: Verificar Despliegue

```bash
# Ver estado de los pods
kubectl get pods -o wide

# Ver logs de un servicio
kubectl logs -f deployment/auth-service

# Hacer health check
for service in auth-service booking-service search-service cart-service reports-service inventory-service commercial-service notification-service payment-service health-copilot; do
  POD=$(kubectl get pod -l app=$service -o jsonpath="{.items[0].metadata.name}")
  echo "Checking $service..."
  kubectl exec $POD -- curl -s http://localhost:8000/health
done
```

## Paso 11: Configurar GitHub Actions

1. Ir a repositorio en GitHub
2. Settings > Secrets and variables > Actions
3. Agrega los siguientes secrets:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_REGION` = us-east-1

## Monitoreo Post-Despliegue

```bash
# Ver métricas de nodos
kubectl top nodes

# Ver métricas de pods
kubectl top pods

# Ver eventos
kubectl get events --sort-by='.lastTimestamp'

# Describir un pod con problemas
kubectl describe pod <pod-name>
```

## Troubleshooting

### Pods en estado Pending
```bash
kubectl describe pod <pod-name>
# Revisar eventos para ver si es por falta de recursos
```

### Pods en CrashLoopBackOff
```bash
kubectl logs <pod-name>
kubectl logs <pod-name> --previous
```

### Problemas de conectividad
```bash
# Verificar security groups
# Verificar que los pods puedan resolver DNS
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default
```

## Costos Estimados (us-east-1)

- **EKS Cluster**: ~$73/mes
- **EC2 Nodes** (3x t3.medium): ~$90/mes
- **RDS** (db.t3.micro): ~$15/mes
- **NAT Gateways** (3): ~$97/mes
- **Load Balancer**: ~$20/mes
- **ECR Storage**: ~$1/mes
- **Total estimado**: ~$296/mes

## Limpieza de Recursos

```bash
# Eliminar recursos de Kubernetes
kubectl delete -f kubernetes/deployments/
kubectl delete -f kubernetes/ingress.yaml

# Destruir infraestructura con Terraform
cd infrastructure/terraform
terraform destroy -var-file=terraform.tfvars

# Eliminar imágenes de ECR (opcional)
for repo in $(aws ecr describe-repositories --query 'repositories[*].repositoryName' --output text); do
  aws ecr delete-repository --repository-name $repo --force
done
```

