variable "lambda_invoke_arn" {
  type = string
}

variable "lambda_function_name" {
  type = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "default_route_rate_limit" {
  description = "Default route request rate limit per second"
  type        = number
  default     = 1

  validation {
    condition     = var.default_route_rate_limit > 0
    error_message = "The default route rate limit must be greater than zero."
  }
}

variable "default_route_burst_limit" {
  description = "Default route burst request limit"
  type        = number
  default     = 2

  validation {
    condition     = var.default_route_burst_limit > 0 && floor(var.default_route_burst_limit) == var.default_route_burst_limit
    error_message = "The default route burst limit must be a positive whole number."
  }
}
