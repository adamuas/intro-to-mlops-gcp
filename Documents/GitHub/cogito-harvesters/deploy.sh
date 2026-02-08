#!/bin/bash
# Cogito Harvesters Deployment Script
# Project: synapse-ai-platform

set -e

PROJECT_ID="synapse-ai-platform"
REGION="europe-west2"
VERTEX_LOCATION="us-east1"
VERTEX_EMBEDDING_ENDPOINT_ID="3219548167011827712"
GLINER_ENDPOINT="https://gliner2-service-634181660442.us-central1.run.app"

echo "=== Cogito Harvesters Deployment ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    pubsub.googleapis.com \
    secretmanager.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com

# Create Pub/Sub topics (if not exist)
echo "Creating Pub/Sub topics..."
gcloud pubsub topics create twitter-raw-data --project=$PROJECT_ID 2>/dev/null || echo "Topic twitter-raw-data already exists"
gcloud pubsub topics create news-raw-data --project=$PROJECT_ID 2>/dev/null || echo "Topic news-raw-data already exists"

# Build and push Docker images for linux/amd64 (Cloud Run requires x86_64)
echo ""
echo "Building Twitter Harvester (linux/amd64)..."
docker build --platform linux/amd64 -t gcr.io/$PROJECT_ID/twitter-harvester:latest ./twitter-harvester

echo ""
echo "Building Gazette Harvester (linux/amd64)..."
docker build --platform linux/amd64 -t gcr.io/$PROJECT_ID/gazette-harvester:latest ./gazette-harvester

echo ""
echo "Pushing images to GCR..."
docker push gcr.io/$PROJECT_ID/twitter-harvester:latest
docker push gcr.io/$PROJECT_ID/gazette-harvester:latest

# Deploy Twitter Harvester
echo ""
echo "Deploying Twitter Harvester to Cloud Run..."
gcloud run deploy twitter-harvester \
    --image gcr.io/$PROJECT_ID/twitter-harvester:latest \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --timeout 300 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,PUBSUB_TOPIC=socials-harvester-output,GLINER_ENDPOINT=$GLINER_ENDPOINT,VERTEX_LOCATION=$VERTEX_LOCATION,VERTEX_EMBEDDING_ENDPOINT_ID=$VERTEX_EMBEDDING_ENDPOINT_ID" \
    --set-secrets "APIFY_API_TOKEN=synapse-dev-apify-api-key:latest"

# Deploy Gazette Harvester
echo ""
echo "Deploying Gazette Harvester to Cloud Run..."
gcloud run deploy gazette-harvester \
    --image gcr.io/$PROJECT_ID/gazette-harvester:latest \
    --region $REGION \
    --platform managed \
    --allow-unauthenticated \
    --memory 1Gi \
    --timeout 300 \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,PUBSUB_TOPIC=socials-harvester-output,GLINER_ENDPOINT=$GLINER_ENDPOINT,VERTEX_LOCATION=$VERTEX_LOCATION,VERTEX_EMBEDDING_ENDPOINT_ID=$VERTEX_EMBEDDING_ENDPOINT_ID" \
    --set-secrets "NEWS_API_KEY=synapse-dev-news-api-key:latest"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Service URLs:"
gcloud run services describe twitter-harvester --region=$REGION --format='value(status.url)'
gcloud run services describe gazette-harvester --region=$REGION --format='value(status.url)'
