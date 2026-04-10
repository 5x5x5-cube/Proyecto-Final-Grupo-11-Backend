#!/bin/bash

echo "Configurando HTTPS para el backend..."

# 1. Crear certificado autofirmado
echo "Creando certificado SSL autofirmado..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key -out tls.crt \
  -subj "/CN=*.elb.us-east-1.amazonaws.com/O=ProyectoFinal"

# 2. Crear secret en Kubernetes
echo "Creando secret TLS en Kubernetes..."
kubectl create secret tls tls-secret \
  --key tls.key \
  --cert tls.crt \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Actualizar el servicio de NGINX Ingress para exponer puerto 443
echo "Actualizando servicio NGINX Ingress..."
kubectl patch svc ingress-nginx-controller -n ingress-nginx -p '{"spec":{"type":"LoadBalancer","ports":[{"name":"http","port":80,"protocol":"TCP","targetPort":"http"},{"name":"https","port":443,"protocol":"TCP","targetPort":"https"}]}}'

# 4. Actualizar ingress para usar TLS
echo "Actualizando ingress con TLS..."
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-gateway
  annotations:
    nginx.ingress.kubernetes.io/enable-cors: "true"
    nginx.ingress.kubernetes.io/cors-allow-origin: "*"
    nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, PUT, DELETE, OPTIONS"
    nginx.ingress.kubernetes.io/cors-allow-headers: "DNT,X-CustomHeader,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Authorization"
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "false"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - "*.elb.us-east-1.amazonaws.com"
    secretName: tls-secret
  rules:
  - http:
      paths:
      - path: /api/v1/auth
        pathType: Prefix
        backend:
          service:
            name: auth-service
            port:
              number: 80
      - path: /api/v1/search
        pathType: Prefix
        backend:
          service:
            name: search-service
            port:
              number: 80
      - path: /api/v1/cart
        pathType: Prefix
        backend:
          service:
            name: cart-service
            port:
              number: 80
      - path: /api/v1/booking
        pathType: Prefix
        backend:
          service:
            name: booking-service
            port:
              number: 80
      - path: /api/v1/payment
        pathType: Prefix
        backend:
          service:
            name: payment-service
            port:
              number: 80
      - path: /api/v1/notification
        pathType: Prefix
        backend:
          service:
            name: notification-service
            port:
              number: 80
      - path: /api/v1/inventory
        pathType: Prefix
        backend:
          service:
            name: inventory-service
            port:
              number: 80
      - path: /api/v1/health-copilot
        pathType: Prefix
        backend:
          service:
            name: health-copilot
            port:
              number: 80
EOF

echo ""
echo "✅ HTTPS configurado!"
echo ""
echo "Esperando a que el Load Balancer se actualice..."
sleep 10

# Obtener la URL del Load Balancer
LB_URL=$(kubectl get svc ingress-nginx-controller -n ingress-nginx -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')

echo ""
echo "🔒 Backend disponible en:"
echo "   HTTP:  http://$LB_URL/api/v1/"
echo "   HTTPS: https://$LB_URL/api/v1/"
echo ""
echo "⚠️  NOTA: El certificado es autofirmado, los navegadores mostrarán advertencia de seguridad."
echo "   Para producción, necesitas un dominio propio y certificado válido de ACM."
echo ""
echo "Actualiza el frontend con la nueva URL HTTPS:"
echo "   VITE_API_BASE_URL=https://$LB_URL/api/v1"
