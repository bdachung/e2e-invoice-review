resource "azurerm_storage_account" "this" {
  name                            = "stinvoicereview547ea842"
  location                        = azurerm_resource_group.this.location
  resource_group_name             = azurerm_resource_group.this.name
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  allow_nested_items_to_be_public = false
  min_tls_version                 = "TLS1_0"
}

resource "azurerm_storage_share" "reviewdata" {
  name               = "reviewdata"
  storage_account_id = azurerm_storage_account.this.id
  quota              = 10
}

resource "azurerm_container_app_environment_storage" "reviewdata" {
  name                         = "reviewdata"
  container_app_environment_id = azurerm_container_app_environment.this.id
  account_name                 = azurerm_storage_account.this.name
  access_key                   = azurerm_storage_account.this.primary_access_key
  share_name                   = azurerm_storage_share.reviewdata.name
  access_mode                  = "ReadWrite"

  # The Container Apps API never returns the account key, so Terraform cannot
  # verify it after import; the value in config is the storage account key.
  lifecycle {
    ignore_changes = [access_key]
  }
}
