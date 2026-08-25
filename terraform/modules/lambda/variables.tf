variable "dynamodb_table_arn" {
  type = string
}

variable "dynamodb_kms_key_arn" {
  description = "ARN of the KMS key used to encrypt the DynamoDB table"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}
variable "data_bucket_name" {
  description = "S3 bucket for storing request data"
  type        = string
}

variable "reserved_concurrency" {
  description = "Reserved concurrent executions for the Lambda function"
  type        = number
  default     = 2

  validation {
    condition     = var.reserved_concurrency > 0 && floor(var.reserved_concurrency) == var.reserved_concurrency
    error_message = "Reserved concurrency must be a positive whole number."
  }
}
