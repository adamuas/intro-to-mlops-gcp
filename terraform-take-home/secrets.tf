
# (4) When do you need secrets? 
# resource "google_secret_manager_secret" "elastic_username" {
#   secret_id = "cogito-${var.env}-api-key"
#   project   = var.project_id

#   labels = {
#     env       = "${var.env}"
#     terraform = true
#   }

#   replication {
#     user_managed {
#       replicas {
#         location = "us-east1"
#       }
#       replicas {
#         location = "us-central1"
#       }
#     }
#   }
# }