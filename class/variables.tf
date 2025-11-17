

#######################################################################
# Synapse AI — Terraform Foundation for Google Cloud (GCP)
#######################################################################


variable "env" {
  description = "env"
  default     = "dev"
}

variable "project_id" {
  description = "project_id"
  default     = "synapse-ai-platform"
}

variable "region" {
  description = "region for the api"
  default     = "us-east1"
}

variable "zone" {
  description = "availability zone"
  default     = "us-east1-b"
}
