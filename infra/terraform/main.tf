resource "azurerm_resource_group" "this" {
  name     = "rg-invoice-review"
  location = var.location
}

resource "azurerm_log_analytics_workspace" "this" {
  name                = "law-invoice-review"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name

  # The API reports this value as null (inherited default), so state cannot
  # store it; ignore to avoid a perpetual one-attribute diff.
  lifecycle {
    ignore_changes = [local_authentication_enabled]
  }
}

resource "azurerm_container_app_environment" "this" {
  name                       = "cae-invoice-review"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.this.id

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

resource "azurerm_container_registry" "this" {
  name                = "invoicereview547ea842"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  sku                 = "Basic"
  admin_enabled       = true
}
