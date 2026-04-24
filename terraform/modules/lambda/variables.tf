variable "dynamodb_table_arn" {
  type = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}
variable "data_bucket_name" {
  description = "S3 bucket for storing request data"
  type        = string
}