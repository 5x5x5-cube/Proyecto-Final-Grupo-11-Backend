# Guía de Despliegue - Proyecto Final

## Prerrequisitos (solo la primera vez)

1. **AWS CLI v2**: [Descargar](https://awscli.amazonaws.com/AWSCLIV2.msi)
2. **Terraform**: [Descargar](https://developer.hashicorp.com/terraform/downloads)
3. **kubectl**: [Descargar](https://dl.k8s.io/release/v1.31.0/bin/windows/amd64/kubectl.exe)
4. **Docker Desktop**: [Descargar](https://www.docker.com/products/docker-desktop)
5. **Git Bash**: Incluido con [Git for Windows](https://gitforwindows.org/)
6. **aws-iam-authenticator** (requerido en Windows):
   ```bash
   mkdir -p ~/bin
   curl -Lo ~/bin/aws-iam-authenticator.exe \
     https://github.com/kubernetes-sigs/aws-iam-authenticator/releases/download/v0.6.26/aws-iam-authenticator_0.6.26_windows_amd64.exe
   ```
   > **¿Por qué?** AWS CLI v2 en Windows es un bundle PyInstaller que crashea al ser
   > ejecutado como subproceso por kubectl. `aws-iam-authenticator` es un binario Go
   > nativo que no tiene este problema. `deploy.sh` lo detecta automáticamente.

7. **Configurar credenciales AWS**:
   ```bash
   aws configure
   # AWS Access Key ID: <tu-key>
   # AWS Secret Access Key: <tu-secret>
   # Default region name: us-east-1
   # Default output format: json
   ```

---

## Crear TODO desde cero

Abre **Git Bash** y ejecuta desde la raíz del proyecto:

### Paso 1: Crear infraestructura con Terraform (~15-20 min)

```bash
cd infrastructure/terraform
terraform init
terraform apply
# Escribir "yes" cuando pregunte
```

Terraform crea:
- **VPC** con subnets públicas y privadas
- **EKS** cluster con 1 nodo t3.small
- **RDS** PostgreSQL
- **ElastiCache** Redis
- **SQS** cola de sincronización de hoteles
- **ECR** repositorios Docker por servicio
- **IAM roles** para IRSA (inventory-service, search-service)

> **IMPORTANTE**: No interrumpir. Si falla por error de red, ejecutar `terraform apply` de nuevo.
> Si aparece error de lock: `terraform force-unlock <LOCK-ID>`

### Paso 2: Desplegar aplicaciones

```bash
cd ../..   # volver a la raíz del proyecto
./deploy.sh
```

El script `deploy.sh` realiza automáticamente:
1. Genera kubeconfig con `aws-iam-authenticator` (evita bug de PyInstaller en Windows)
2. Verifica acceso al cluster (`kubectl get nodes`)
3. Lee outputs de Terraform (DB endpoint, Redis, SQS)
4. Crea **Secrets** de Kubernetes por servicio:
   - `auth-service-secrets` → `database-url` (PostgreSQL connection string)
   - `inventory-service-secrets` → `database-url`
5. Crea **ConfigMaps** de Kubernetes por servicio:
   - `cart-service-config` → `redis-url`
   - `notification-service-config` → `redis-url`
   - `inventory-service-config` → `redis-url`, `sqs-queue-url`
   - `search-service-config` → `redis-url`, `sqs-queue-url`
6. Login a ECR y build/push de imágenes Docker
7. Aplica deployments de Kubernetes
8. Aplica Ingress y espera el Load Balancer

### Paso 3: Verificar

```bash
kubectl get pods          # todos deben estar Running
kubectl get svc           # ver servicios
kubectl get ingress       # ver URL del Load Balancer
```

---

## Servicios desplegados

| Servicio | Puerto | Health Check | Secret/ConfigMap |
|----------|--------|-------------|-----------------|
| auth-service | 8000 | /health | `auth-service-secrets` |
| inventory-service | 8000 | /health | `inventory-service-secrets`, `inventory-service-config` |
| search-service | 8000 | /health | `search-service-config` |
| search-worker | — | — | `search-service-config` |
| cart-service | 8000 | /health | `cart-service-config` |
| notification-service | 8000 | /health | `notification-service-config` |
| health-copilot | 8000 | /health | — |

> **Nota**: `t3.small` tiene ~1.4GB RAM disponible. Todos los pods usan `requests: 64Mi`.
> Si se necesitan más servicios (booking, commercial, payment, reports),
> cambiar `node_instance_types` a `["t3.medium"]` en `infrastructure/terraform/variables.tf`
> y ejecutar `terraform apply`.

---

## Actualizar después de cambios en código

Si solo cambiaste código de un servicio (sin cambios en infraestructura):

```bash
# Opción 1: Re-ejecutar todo
./deploy.sh

# Opción 2: Actualizar un solo servicio
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 618246140762.dkr.ecr.us-east-1.amazonaws.com

docker build -t 618246140762.dkr.ecr.us-east-1.amazonaws.com/proyecto-final-dev-<servicio>:latest services/<servicio_dir>/
docker push 618246140762.dkr.ecr.us-east-1.amazonaws.com/proyecto-final-dev-<servicio>:latest

kubectl rollout restart deployment/<servicio>
```

Mapeo de nombres (nombre-servicio → directorio):
- `auth-service` → `services/auth_service/`
- `inventory-service` → `services/inventory_service/`
- `search-service` → `services/search_service/`
- `cart-service` → `services/cart_service/`
- `notification-service` → `services/notification_service/`
- `health-copilot` → `services/health_copilot/`

---

## Destruir TODO (evitar cargos)

```bash
# 1. Eliminar recursos de Kubernetes primero (libera el Load Balancer)
kubectl delete -f kubernetes/ingress.yaml 2>/dev/null
kubectl delete -f kubernetes/deployments/ 2>/dev/null

# 2. Destruir infraestructura
cd infrastructure/terraform
terraform destroy
# Escribir "yes" cuando pregunte
```

> Tarda ~15-20 minutos. **No interrumpir.**
> Si falla por timeout de red, ejecutar `terraform destroy` de nuevo.
> Si queda un lock: `terraform force-unlock <LOCK-ID>`
> Si el Secrets Manager secret queda pendiente de eliminación:
> `aws secretsmanager delete-secret --secret-id proyecto-final-dev-db-password --region us-east-1 --force-delete-without-recovery`

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `terraform destroy/apply` falla por lock | `terraform force-unlock <LOCK-ID>` |
| Error DNS durante terraform | Verificar conexión a internet, reintentar |
| Secret "scheduled for deletion" | `aws secretsmanager delete-secret --secret-id <id> --region us-east-1 --force-delete-without-recovery` |
| kubectl 401 Unauthorized | Verificar que kubeconfig usa `aws-iam-authenticator`, no `aws`. Re-ejecutar `./deploy.sh` |
| `aws.exe` PyInstaller error en kubectl | Instalar `aws-iam-authenticator.exe` en `~/bin/`. El deploy.sh lo usa automáticamente |
| Pods en Pending (Insufficient memory) | Reducir `resources.requests` en YAMLs o cambiar a `t3.medium` |
| ImagePullBackOff | Verificar que la imagen fue construida y subida con `docker push`. Nombre ECR: `proyecto-final-dev-<servicio>` (con guión, no slash) |
| CreateContainerConfigError | Falta Secret o ConfigMap. Verificar con `kubectl describe pod <pod>` y crear los que falten |
| Pods en CrashLoopBackOff | Ver logs: `kubectl logs <pod-name>`. Puede ser error de dependencias en el código |
