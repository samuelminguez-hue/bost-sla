#!/bin/bash
# deploy_cloudrun.sh — lanzar después de que el script Python genere los HTMLs
# Uso: bash deploy_cloudrun.sh
#
# Prerequisito: gcloud CLI instalado y autenticado con una cuenta @masorange.es
#               Sustituir TU_PROYECTO_GCP por el proyecto real antes de usar

PROJECT="TU_PROYECTO_GCP"
REGION="europe-west1"
REPO="bost"
SERVICE="bost-sla-fijo"
IMAGE="$REGION-docker.pkg.dev/$PROJECT/$REPO/sla-fijo:latest"

echo "Desplegando informe SLA Fijo en Cloud Run..."
echo "Proyecto: $PROJECT | Imagen: $IMAGE"

gcloud builds submit \
  --config cloudbuild.yaml \
  --project "$PROJECT" \
  .

echo ""
echo "Despliegue completado."
echo "URL del informe: https://$(gcloud run services describe $SERVICE --region=$REGION --project=$PROJECT --format='value(status.url)' 2>/dev/null || echo '<pendiente>')"
