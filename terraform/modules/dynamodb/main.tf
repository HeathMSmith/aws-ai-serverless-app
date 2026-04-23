data "aws_caller_identity" "current" {}
resource "aws_kms_key" "dynamodb" {
  description             = "KMS key for DynamoDB"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "EnableRootPermissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = "kms:*"
        Resource = "*"
      },
      {
        Sid = "AllowLambdaUseOfKey"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/lambda-ai-serverless-${var.environment}-role"
        }
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })
}
resource "aws_kms_alias" "dynamodb" {
  name          = "alias/dynamodb-app-${var.environment}"
  target_key_id = aws_kms_key.dynamodb.key_id
}
resource "aws_dynamodb_table" "app_table" {
  name         = "ai-serverless-app-table-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"

  attribute {
    name = "request_id"
    type = "S"
  }

  server_side_encryption {
  enabled = true
  kms_key_arn = aws_kms_key.dynamodb.arn
}

  tags = {
    Name        = "ai-serverless-app-table-${var.environment}"
    Environment = var.environment
  }
}
