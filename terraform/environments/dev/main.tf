provider "aws" {
  region = "us-east-1"
}

provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

module "iam" {
  source = "../../modules/iam"
}

module "s3" {
  source      = "../../modules/s3"
  environment = var.environment
}

module "dynamodb" {
  source      = "../../modules/dynamodb"
  environment = var.environment
}

module "lambda" {
  source      = "../../modules/lambda"
  environment = var.environment

  dynamodb_table_arn = module.dynamodb.table_arn
}

module "apigateway" {
  source               = "../../modules/apigateway"
  environment          = var.environment
  lambda_invoke_arn    = module.lambda.invoke_arn
  lambda_function_name = module.lambda.function_name
}
module "frontend" {
  source      = "../../modules/frontend"
  environment = var.environment

  api_endpoint = module.apigateway.api_endpoint

  providers = {
    aws           = aws
    aws.us_east_1 = aws.us_east_1
  }
}