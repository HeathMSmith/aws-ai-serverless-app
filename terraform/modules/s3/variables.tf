variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}
variable "bucket_suffix" {
  description = "Optional suffix appended to the S3 bucket name."
  type        = string
  default     = ""
}