resource "azurerm_container_app" "web" {
  name                         = local.app_name
  resource_group_name          = azurerm_resource_group.this.name
  container_app_environment_id = azurerm_container_app_environment.this.id
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  max_inactive_revisions       = 100
  identity {
    type = "SystemAssigned"
  }

  ingress {
    external_enabled = true
    target_port      = 8000

    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }

  registry {
    server               = azurerm_container_registry.this.login_server
    username             = azurerm_container_registry.this.name
    password_secret_name = "acr-pull-password"
  }
  secret {
    name                = "acr-pull-password"
    key_vault_secret_id = "${azurerm_key_vault.this.vault_uri}secrets/acr-pull-password"
    identity            = "System"
  }
  secret {
    name                = "app-password"
    key_vault_secret_id = "${azurerm_key_vault.this.vault_uri}secrets/app-password"
    identity            = "System"
  }
  secret {
    name                = "session-secret"
    key_vault_secret_id = "${azurerm_key_vault.this.vault_uri}secrets/session-secret"
    identity            = "System"
  }
  secret {
    name                = "azure-openai-api-key"
    key_vault_secret_id = "${azurerm_key_vault.this.vault_uri}secrets/azure-openai-api-key"
    identity            = "System"
  }
  secret {
    name                = "document-intelligence-key"
    key_vault_secret_id = "${azurerm_key_vault.this.vault_uri}secrets/document-intelligence-key"
    identity            = "System"
  }
  secret {
    name                = "database-url"
    key_vault_secret_id = "${azurerm_key_vault.this.vault_uri}secrets/database-url"
    identity            = "System"
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = local.app_name
      image  = var.container_image
      cpu    = 1
      memory = "2Gi"

      env {
        name  = "AUTH_ENABLED"
        value = "true"
      }
      env {
        name        = "APP_PASSWORD"
        secret_name = "app-password"
      }
      env {
        name        = "SESSION_SECRET"
        secret_name = "session-secret"
      }
      env {
        name        = "AZURE_OPENAI_API_KEY"
        secret_name = "azure-openai-api-key"
      }
      env {
        name        = "AZURE_DOCUMENT_INTELLIGENCE_KEY"
        secret_name = "document-intelligence-key"
      }
      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = var.azure_openai_endpoint
      }
      env {
        name  = "AZURE_OPENAI_DEPLOYMENT"
        value = var.azure_openai_deployment
      }
      env {
        name  = "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"
        value = var.azure_document_intelligence_endpoint
      }
      env {
        name        = "DATABASE_URL"
        secret_name = "database-url"
      }
      env {
        name  = "UPLOAD_DIR"
        value = var.upload_dir
      }
      env {
        name  = "FRONTEND_DIST_DIR"
        value = var.frontend_dist_dir
      }

      liveness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health"
        initial_delay           = 10
        interval_seconds        = 30
        timeout                 = 1
        failure_count_threshold = 3
      }

      readiness_probe {
        transport               = "HTTP"
        port                    = 8000
        path                    = "/health"
        initial_delay           = 5
        interval_seconds        = 10
        timeout                 = 1
        failure_count_threshold = 3
        success_count_threshold = 3
      }

      volume_mounts {
        name = "review-data"
        path = "/mnt/data"
      }
    }

    volume {
      name         = "review-data"
      storage_name = "reviewdata"
      storage_type = "AzureFile"
    }
  }

  # The CI workflow (az containerapp update --image) owns the image tag;
  # Terraform never reverts it. Probes carry explicit valid values so app
  # updates do not replay the platform's stored 0 defaults. Secrets are
  # managed by Terraform as Key Vault references (values live in Key Vault);
  # the app's system-assigned identity reads them via Key Vault Secrets User.
  lifecycle {
    ignore_changes = [
      template[0].container[0].image,
    ]
  }
}
