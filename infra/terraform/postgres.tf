resource "azurerm_postgresql_flexible_server" "this" {
  name                = "pg-invoice-547ea842"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  version             = "16"
  sku_name            = "B_Standard_B1ms"
  storage_mb          = 32768
  zone                = "1"
  administrator_login = "invoiceadmin"

  # The administrator password is managed out-of-band by scripts/deploy-azure.ps1.
  # Terraform never reads, writes, or rotates it; these guards keep it that way.
  lifecycle {
    ignore_changes = [
      administrator_password,
      administrator_password_wo,
    ]
  }
}

resource "azurerm_postgresql_flexible_server_database" "this" {
  name      = "invoicereview"
  server_id = azurerm_postgresql_flexible_server.this.id
}

resource "azurerm_postgresql_flexible_server_firewall_rule" "allow_azure_services" {
  name             = "AllowAllAzureServicesAndResourcesWithinAzureIps_2026-8-14_22-31-16"
  server_id        = azurerm_postgresql_flexible_server.this.id
  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}
