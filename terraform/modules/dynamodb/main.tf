resource "aws_dynamodb_table" "app_table" {
  name         = "ai-serverless-app-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"

  attribute {
    name = "request_id"
    type = "S"
  }

  tags = {
    Name        = "ai-serverless-app-table"
    Environment = "dev"
  }
}