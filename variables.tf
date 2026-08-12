variable "openai_api_key" {
  type        = string
  description = "OpenAI API Key"
  sensitive   = true
}

variable "anthropic_api_key" {
  type        = string
  description = "Anthropic API Key for Evals"
  sensitive   = true
}

variable "langfuse_public_key" {
  type        = string
  description = "Langfuse Public Key"
  default     = ""
  sensitive   = true
}

variable "langfuse_secret_key" {
  type        = string
  description = "Langfuse Secret Key"
  default     = ""
  sensitive   = true
}

variable "langfuse_host" {
  type        = string
  description = "Langfuse Host URL"
  default     = "https://us.cloud.langfuse.com"
}

variable "langfuse_base_url" {
  type        = string
  description = "Langfuse Base URL"
  default     = "https://us.cloud.langfuse.com"
}