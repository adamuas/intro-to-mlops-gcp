
/**
Cognitive Service  
**/

# Service Account
module "service_accounts" {
  source     = "terraform-google-modules/service-accounts/google"
  version    = "~> 4.1.1"
  project_id = var.project_id
  prefix     = "cogito-${var.env}"
  names      = ["gemma2b"]
  project_roles = [
    "cogito-372313=>roles/storage.objectCreator",
    "cogito-372313=>roles/workflows.invoker",
    "cogito-372313=>roles/pubsub.publisher",
    "cogito-372313=>roles/secretmanager.secretAccessor"

  ]
}

# Deploy QWEN
resource "google_vertex_ai_endpoint_with_model_garden_deployment" "deploy_qwen" {
  hugging_face_model_id = "Qwen/Qwen3-0.6B"
  location              = var.region
  model_config {
    accept_eula = true
  }
}

# Deploy Gemma
resource "google_vertex_ai_endpoint_with_model_garden_deployment" "deploy_gemma2b" {
  publisher_model_name = "publishers/google/models/gemma@gemma-1.1-2b-it"
  location             = var.region
  model_config {
    accept_eula = true
  }
  deploy_config {
    dedicated_resources {
      machine_spec {
        machine_type      = "g2-standard-12"
        # accelerator_type  = "?" # (3) Which Accelerator do you need that works with g2-standard-12
        accelerator_count = 1
      }
      min_replica_count = 1
    }
  }
}