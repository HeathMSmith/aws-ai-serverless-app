provider "aws" {
  region = "us-east-1"
}

module "iam" {
  source = "../../modules/iam"
}

module "s3" {
  source = "../../modules/s3"
}

module "dynamodb" {
  source = "../../modules/dynamodb"
}

module "lambda" {
  source = "../../modules/lambda"

  dynamodb_table_arn = module.dynamodb.table_arn
}

module "apigateway" {
  source = "../../modules/apigateway"

  lambda_invoke_arn    = module.lambda.invoke_arn
  lambda_function_name = module.lambda.function_name
}