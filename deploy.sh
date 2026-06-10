#!/bin/bash
# Redboard — Cloud Run deployment script
# Run from your redboard folder: bash deploy.sh

set -e

PROJECT_ID="apt-diode-498606-j6"
REGION="us-central1"
SERVICE_NAME="redboard"
IMAGE="gcr.io/$PROJECT_ID/$SERVICE_NAME"

echo ""
echo "=== Redboard Cloud Run Deployment ==="
echo "Project: $PROJECT_ID"
echo "Region:  $REGION"
echo "Image:   $IMAGE"
echo ""

# Load env vars from .env for the deploy command
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Copy .env.example and fill in your values."
  exit 1
fi

# Read keys from .env
GEMINI_KEY=$(grep "^GEMINI_API_KEY=" .env | cut -d '=' -f2-)
SECRET_KEY=$(grep "^SECRET_KEY=" .env | cut -d '=' -f2-)
RESEND_KEY=$(grep "^RESEND_API_KEY=" .env | cut -d '=' -f2-)
FROM_EMAIL=$(grep "^FROM_EMAIL=" .env | cut -d '=' -f2-)
FROM_NAME=$(grep "^FROM_NAME=" .env | cut -d '=' -f2-)

if [ -z "$GEMINI_KEY" ]; then
  echo "ERROR: GEMINI_API_KEY not found in .env"
  exit 1
fi

if [ -z "$SECRET_KEY" ]; then
  echo "ERROR: SECRET_KEY not found in .env — generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
  exit 1
fi

echo "Step 1: Setting project..."
gcloud config set project $PROJECT_ID

echo "Step 2: Enabling required APIs..."
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com --quiet

echo "Step 3: Building and pushing container image..."
gcloud builds submit --tag $IMAGE --quiet

echo "Step 4: Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --timeout 300 \
  --concurrency 10 \
  --set-env-vars "GEMINI_API_KEY=${GEMINI_KEY},SECRET_KEY=${SECRET_KEY},RESEND_API_KEY=${RESEND_KEY},FROM_EMAIL=${FROM_EMAIL},FROM_NAME=${FROM_NAME},GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=false,DATABASE_URL=sqlite:////app/data/redboard.db,ALLOWED_ORIGINS=https://redboard.dev" \
  --quiet

echo ""
echo "=== Deployment complete! ==="
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
echo "Live URL: $SERVICE_URL"
echo ""
echo "Next steps:"
echo "  1. Test the URL above in your browser"
echo "  2. Update ALLOWED_ORIGINS if you have a custom domain"
echo "  3. Add custom domain in Cloud Run console if you bought redboard.dev"