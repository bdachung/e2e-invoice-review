terraform {
  required_version = "= 1.15.9"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "= 4.80.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-invoice-review-tfstate"
    storage_account_name = "stinvoicereviewtfstate"
    container_name       = "tfstate"
    key                  = "invoice-review.tfstate"
    use_azuread_auth     = true
  }
}
