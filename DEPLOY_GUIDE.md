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

### Paso 1: Crear infraestructura con Terraform

```bash
cd infrastructure/terraform
terraform init
terraform apply
```

> Terraform crea: VPC, EKS, RDS, ElastiCache, SQS, ECR, IAM roles.
> Tarda ~15-20 minutos. **No interrumpir.**

### Paso 2: Desplegar aplicaciones

```bash
cd ../..   # volver a la raíz del proyecto
./deploy.sh
```

> El script automáticamente:
> - Configura kubectl con aws-iam-authenticator
> - Verifica acceso al cluster
> - Crea Secrets y ConfigMaps en Kubernetes
> - Construye y sube imágenes Docker a ECR
> - Despliega todos los servicios
> - Despliega el Ingress y muestra la URL del Load Balancer

### Paso 3: Verificar

```bash
kubectl get pods          # todos deben estar Running
kubectl get svc           # ver servicios
kubectl get ingress       # ver URL del Load Balancer
```

---

## Actualizar después de cambios en código

Si solo cambiaste código de un servicio (sin cambios en infraestructura):

```bash
# Desde la raíz del proyecto
./deploy.sh
```

O para actualizar un solo servicio:

```bash
# Login a ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 618246140762.dkr.ecr.us-east-1.amazonaws.com

# Build y push
docker build -t 618246140762.dkr.ecr.us-east-1.amazonaws.com/proyecto-final-dev/<servicio>:latest services/<servicio>/
docker push 618246140762.dkr.ecr.us-east-1.amazonaws.com/proyecto-final-dev/<servicio>:latest

# Forzar re-deploy
kubectl rollout restart deployment/<servicio>
```

---

## Destruir TODO (evitar cargos)

```bash
# 1. Eliminar recursos de Kubernetes primero (libera el Load Balancer)
kubectl delete -f kubernetes/ingress.yaml
kubectl delete -f kubernetes/deployments/

# 2. Destruir infraestructura
cd infrastructure/terraform
terraform destroy
```

> Tarda ~15-20 minutos. **No interrumpir.**
> Si falla por timeout de red, ejecutar `terraform destroy` de nuevo.
> Si queda un lock: `terraform force-unlock <LOCK-ID>`

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `terraform destroy` falla por lock | `terraform force-unlock <ID>` |
| Error DNS durante terraform | Verificar internet, reintentar |
| Secret de Secrets Manager "scheduled for deletion" | `aws secretsmanager delete-secret --secret-id proyecto-final-dev-db-password --region us-east-1 --force-delete-without-recovery` |
| kubectl 401 Unauthorized | Verificar que el kubeconfig usa `aws-iam-authenticator`, no `aws` |
| `aws.exe` PyInstaller error | Usar `aws-iam-authenticator.exe` en kubeconfig (deploy.sh lo hace automáticamente) |
