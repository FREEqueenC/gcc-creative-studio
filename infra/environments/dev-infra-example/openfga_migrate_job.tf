resource "google_cloud_run_v2_job" "openfga_migrate" {
  provider = google-beta
  name     = "${var.environment}-openfga-migrate"
  location = var.gcp_region
  project  = var.gcp_project_id

  template {
    template {
      containers {
        image = "openfga/openfga:latest"
        args = [
          "migrate"
        ]
        
        env {
          name  = "OPENFGA_DATASTORE_ENGINE"
          value = "postgres"
        }
        
        env {
          name = "OPENFGA_DATASTORE_URI"
          value_source {
            secret_key_ref {
              secret  = module.creative_studio_platform.openfga_db_uri_secret_id
              version = "latest"
            }
          }
        }
        
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
      
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [module.creative_studio_platform.cloud_sql_connection_name]
        }
      }

      max_retries = 3
      timeout     = "600s"
    }
  }
  
  depends_on = [module.creative_studio_platform]
}
