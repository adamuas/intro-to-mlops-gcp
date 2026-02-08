#!/bin/bash
# Deploy Cogito Harvester Workflow
# This workflow routes requests to the appropriate harvester based on source_type

set -e

PROJECT_ID="synapse-ai-platform"
REGION="us-east1"  # Keep same region as existing workflow
WORKFLOW_NAME="cogito-harvester-workflow"

echo "=== Deploying Cogito Harvester Workflow ==="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Workflow: $WORKFLOW_NAME"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Deploy the workflow
echo "Deploying workflow..."
gcloud workflows deploy $WORKFLOW_NAME \
    --location=$REGION \
    --source=cogito-harvester-workflow.yaml \
    --description="Routes ingestion requests to Twitter or Gazette harvester based on source_type"

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "Workflow URL:"
echo "https://console.cloud.google.com/workflows/workflow/$REGION/$WORKFLOW_NAME?project=$PROJECT_ID"
echo ""
echo "To execute the workflow:"
echo "gcloud workflows execute $WORKFLOW_NAME --location=$REGION --data='{\"query\":\"test\",\"source_type\":\"apify-twitter\",\"project_id\":\"test123\"}'"
