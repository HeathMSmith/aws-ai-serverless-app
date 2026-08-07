variable "environment" {
  type = string
}

variable "api_endpoint" {
  description = "API Gateway endpoint"
  type        = string
}

variable "use_custom_domain" {
  description = "Whether to configure a custom domain with Route 53 and ACM."
  type        = bool
  default     = false
}
variable "bucket_suffix" {
  description = "Optional suffix appended to the frontend S3 bucket name."
  type        = string
  default     = ""
}