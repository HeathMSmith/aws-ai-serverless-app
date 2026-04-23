terraform {
  backend "s3" {
    bucket         = "hms-tfstate-ai-serverless-app"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}