variable "subscription_id" {
  description = "Azure subscription ID hosting the Invoice Review deployment."
  type        = string
  default     = "547ea842-2fe2-41f8-95a4-80bd9f69961b"
}

variable "location" {
  description = "Azure region used by the existing deployment."
  type        = string
  default     = "southeastasia"
}

variable "container_image" {
  description = "Current deployed image tag. The CI workflow updates it; Terraform ignores image drift."
  type        = string
  default     = "invoicereview547ea842.azurecr.io/invoice-review-web:8c7915f71398378219d536eb4d82284000c84a85"
}

variable "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint used by the app (existing external AI resource)."
  type        = string
  default     = "https://invoice-review-foundry-hungbd.openai.azure.com/openai/v1"
}

variable "azure_openai_deployment" {
  description = "Azure OpenAI deployment name used by the app."
  type        = string
  default     = "gpt-4.1-mini"
}

variable "azure_document_intelligence_endpoint" {
  description = "Azure Document Intelligence endpoint used by the app (existing external AI resource)."
  type        = string
  default     = "https://di-invoice-review-77ee6.cognitiveservices.azure.com/"
}

variable "upload_dir" {
  description = "Container path where uploads are mounted."
  type        = string
  default     = "/mnt/data/uploads"
}

variable "frontend_dist_dir" {
  description = "Container path where the built frontend is served from."
  type        = string
  default     = "/app/frontend-dist"
}
