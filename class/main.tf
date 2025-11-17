#######################################################################
# Synapse AI — Terraform Foundation for Google Cloud (GCP)
#######################################################################


variable "service_name" {
  description = "Service name"
  default     = "onnx-sentiment"
}


resource "google_vertex_ai_endpoint_with_model_garden_deployment" "deploy" {
  hugging_face_model_id = "Qwen/Qwen3-0.6B"
  location             = "us-east1"
  model_config {
    accept_eula = true
  }

  deploy_config {
    dedicated_resources {
      machine_spec {
        machine_type      = "g2-standard-4"
        accelerator_type  = "NVIDIA_L4"
        accelerator_count = 1
      }
      min_replica_count = 1
      spot = true
    }
  }
}