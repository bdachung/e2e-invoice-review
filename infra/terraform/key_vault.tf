resource "azurerm_key_vault" "this" {
  name                       = "kv-invoice-547ea842"
  location                   = azurerm_resource_group.this.location
  resource_group_name        = azurerm_resource_group.this.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = true
  rbac_authorization_enabled = true
}

# Grants the Container App's system-assigned identity read access to the
# vault so its secret references resolve when a revision is created.
resource "azurerm_role_assignment" "container_app_key_vault_secrets_user" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_container_app.web.identity[0].principal_id
}


# Grants the operator write access so secrets can be seeded and rotated
# without ever putting values in Terraform configuration or state.
resource "azurerm_role_assignment" "secrets_officer" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = var.key_vault_secrets_officer_object_id
}