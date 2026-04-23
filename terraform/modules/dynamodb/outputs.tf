output "table_name" {
  value = aws_dynamodb_table.app_table.name
}

output "table_arn" {
  value = aws_dynamodb_table.app_table.arn
}