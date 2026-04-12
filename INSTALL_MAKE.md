# 📦 Instalación de Make en Windows

Make es una herramienta que automatiza la ejecución de comandos. Este proyecto incluye un **Makefile** que simplifica el despliegue en AWS.

## 🪟 Opción 1: Chocolatey (Recomendado)

### 1. Instalar Chocolatey

Abre **PowerShell como Administrador** y ejecuta:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

### 2. Instalar Make

```powershell
choco install make -y
```

### 3. Verificar instalación

```powershell
make --version
```

Deberías ver algo como: `GNU Make 4.x`

---

## 🔧 Opción 2: Git Bash (Si ya tienes Git instalado)

Si instalaste **Git for Windows**, ya tienes Make incluido.

### 1. Abre Git Bash

Busca "Git Bash" en el menú de inicio

### 2. Navega a tu proyecto

```bash
cd /c/Users/ronal/Documents/proyecto2/Proyecto-Final-Grupo-11-Backend
```

### 3. Ejecuta comandos Make

```bash
make help
```

---

## 🐧 Opción 3: WSL (Windows Subsystem for Linux)

### 1. Instalar WSL

En PowerShell como Administrador:

```powershell
wsl --install
```

Reinicia tu computadora.

### 2. Abrir Ubuntu (o tu distro instalada)

### 3. Instalar Make

```bash
sudo apt update
sudo apt install make -y
```

### 4. Navegar a tu proyecto

```bash
cd /mnt/c/Users/ronal/Documents/proyecto2/Proyecto-Final-Grupo-11-Backend
```

### 5. Usar Make

```bash
make help
```

---

## 🎯 Opción 4: Descargar binario directo

### 1. Descargar Make para Windows

Ve a: https://gnuwin32.sourceforge.net/packages/make.htm

Descarga: **Complete package, except sources**

### 2. Instalar

Ejecuta el instalador y sigue las instrucciones.

### 3. Agregar al PATH

1. Busca "Variables de entorno" en Windows
2. Edita la variable `Path`
3. Agrega: `C:\Program Files (x86)\GnuWin32\bin`
4. Reinicia PowerShell

### 4. Verificar

```powershell
make --version
```

---

## ✅ Verificar que funciona

Una vez instalado Make, ejecuta:

```bash
make help
```

Deberías ver el menú de comandos disponibles:

```
==========================================
  COMANDOS DE DESARROLLO LOCAL
==========================================
  make setup         - Instalar dependencias + configurar git hooks
  make install       - Instalar dependencias de todos los servicios
  ...

==========================================
  COMANDOS DE DESPLIEGUE AWS
==========================================
  make aws-setup     - Configurar AWS CLI y verificar credenciales
  make aws-deploy    - Desplegar infraestructura completa en AWS
  ...
```

---

## 🚀 Uso del Makefile

### Despliegue completo en AWS (un solo comando):

```bash
make deploy-all
```

Esto ejecuta automáticamente:
1. ✅ Verifica herramientas (AWS CLI, Terraform, kubectl)
2. ✅ Crea backend de Terraform (S3 + DynamoDB)
3. ✅ Despliega infraestructura (VPC, EKS, RDS, Redis, SQS)
4. ✅ Construye imágenes Docker
5. ✅ Sube imágenes a ECR
6. ✅ Configura kubectl
7. ✅ Crea secrets y configmaps
8. ✅ Despliega servicios en Kubernetes

### Comandos individuales:

```bash
# Ver plan de Terraform sin aplicar
make aws-plan

# Solo desplegar infraestructura
make aws-deploy

# Solo configurar Kubernetes
make k8s-setup

# Ver estado de pods
make k8s-status

# Ver logs
make k8s-logs

# Destruir todo
make aws-destroy
```

---

## 🐛 Problemas comunes

### Error: "make: command not found"

- **Solución**: Make no está en el PATH. Reinicia PowerShell o agrega la ruta manualmente.

### Error: "No rule to make target"

- **Solución**: Asegúrate de estar en el directorio raíz del proyecto donde está el `Makefile`.

### Error en comandos con `@`

- **Solución**: Usa Git Bash o WSL. PowerShell nativo tiene problemas con algunos comandos de Make.

---

## 💡 Recomendación

Para Windows, la mejor opción es **Git Bash** (Opción 2) porque:
- ✅ Ya lo tienes si instalaste Git
- ✅ Soporta todos los comandos de Make
- ✅ No requiere permisos de administrador
- ✅ Compatible con scripts bash

---

## 📚 Siguiente paso

Una vez instalado Make, ve a la [Guía de Despliegue](DEPLOYMENT.md) o ejecuta:

```bash
make help
```
