resource "aws_kms_key" "dynamodb" {
  description             = "KMS key for DynamoDB encryption"
  deletion_window_in_days = 7
  enable_key_rotation     = true
}
resource "aws_kms_alias" "dynamodb" {
  name          = "alias/dynamodb-app"
  target_key_id = aws_kms_key.dynamodb.key_id
}
resource "aws_dynamodb_table" "app_table" {
  name         = "ai-serverless-app-table"
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
    Name        = "ai-serverless-app-table"
    Environment = "dev"
  }
}
