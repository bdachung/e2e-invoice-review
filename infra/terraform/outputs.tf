output "app_url" {
  description = "HTTPS URL of the Invoice Review Container App."
  value       = "https://${azurerm_container_app.web.ingress[0].fqdn}"
}

output "resource_group_id" {
  value = azurerm_resource_group.this.id
}

output "container_app_id" {
  value = azurerm_container_app.web.id
}

output "postgresql_server_id" {
  value = azurerm_postgresql_flexible_server.this.id
}

output "storage_account_id" {
  value = azurerm_storage_account.this.id
}
