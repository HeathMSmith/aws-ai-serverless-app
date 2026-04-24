resource "aws_iam_role" "lambda_role" {
  name = "lambda-ai-serverless-${var.environment}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

data "aws_iam_policy_document" "lambda_policy" {
  statement {
    effect = "Allow"

    actions = [
      "dynamodb:PutItem"
    ]

    resources = [var.dynamodb_table_arn]
  }

  statement {
    effect = "Allow"

    actions = [
      "bedrock:InvokeModel"
    ]

    resources = ["*"]
  }
    statement {
        effect = "Allow"
    
        actions = [
        "s3:PutObject"
        ]
        resources = ["arn:aws:s3:::${var.data_bucket_name}/*"]
    }
}

resource "aws_iam_policy" "lambda_dynamodb_policy" {
  name   = "lambda-dynamodb-write-policy-${var.environment}"
  policy = data.aws_iam_policy_document.lambda_policy.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_dynamodb_attach" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_dynamodb_policy.arn
}

resource "aws_lambda_function" "app_lambda" {
  function_name = "ai-serverless-app-${var.environment}-lambda"
  role          = aws_iam_role.lambda_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"

  filename         = "${path.module}/../../../app/lambda/package/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../../../app/lambda/package/lambda.zip")

  timeout = 10

  environment {
    variables = {
      TABLE_NAME = "ai-serverless-app-table-${var.environment}"
      DATA_BUCKET = var.data_bucket_name
    }
  }
}