import json
import uuid
import boto3
import logging
import os
import traceback
from datetime import datetime

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime")
s3 = boto3.client("s3")

table_name = os.environ["TABLE_NAME"]
table = dynamodb.Table(table_name)

data_bucket = os.environ["DATA_BUCKET"]

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    try:
        body = event.get("body")

        if isinstance(body, str):
            body = json.loads(body)
        elif body is None:
            body = {}

        # --- Input Validation ---
        if "input" not in body:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Missing required field: input"
                })
            }

        user_input = body["input"]

        if not isinstance(user_input, str) or len(user_input.strip()) == 0:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Input must be a non-empty string"
                })
            }

        if len(user_input) > 500:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Input exceeds 500 character limit"
                })
            }

        request_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        logger.info(f"Processing request_id={request_id}")

        # --- Bedrock Call ---
        prompt = f"Respond clearly and concisely: {user_input}"

        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 100,
                "temperature": 0.7
            })
        )

        response_body = json.loads(response["body"].read())
        ai_output = response_body["content"][0]["text"]

        logger.info(f"Bedrock response received for request_id={request_id}")

        # --- Store in DynamoDB ---
        item = {
            "request_id": request_id,
            "input": user_input,
            "output": ai_output,
            "timestamp": timestamp,
            "status": "COMPLETED"
        }

        table.put_item(Item=item)
        
        # --- Store in S3 ---
        object_key = f"requests/{timestamp}-{request_id}.json"

        s3.put_object(
            Bucket=data_bucket,
            Key=object_key,
            Body=json.dumps(item),
            ContentType="application/json"
        )

        logger.info(f"Stored request in S3: {object_key}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "request_id": request_id,
                "response": ai_output
            })
        }

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        logger.error(traceback.format_exc())

        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }