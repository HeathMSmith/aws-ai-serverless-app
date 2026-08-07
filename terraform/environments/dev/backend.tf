terraform {
  backend "s3" {
    bucket         = "hms-terraform-state-portfolio"
    key            = "ai-serverlessapp/dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "hms-terraform-locks"
    encrypt        = true
  }
}