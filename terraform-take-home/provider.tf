#######################################################################
# Synapse AI — Terraform Foundation for Google Cloud (GCP)
#######################################################################
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
    #   version = "?" (1) (Your Task - Which Version)
    }
    google-beta = {
      source  = "hashicorp/google-beta"
    #   version = "?" (2) (Your Task - Resolve Version)
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
