import importlib.util
import io
import json
import logging
import os
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch


HANDLER_PATH = Path(__file__).resolve().parents[1] / "app" / "lambda" / "handler.py"


class LambdaHandlerTests(unittest.TestCase):
    def setUp(self):
        root_logger = logging.getLogger()
        original_root_logger_level = root_logger.level
        self.addCleanup(root_logger.setLevel, original_root_logger_level)

        self.table = MagicMock(name="table")
        self.dynamodb = MagicMock(name="dynamodb")
        self.dynamodb.Table.return_value = self.table
        self.bedrock = MagicMock(name="bedrock")
        self.s3 = MagicMock(name="s3")

        fake_boto3 = MagicMock(name="boto3")
        fake_boto3.resource.return_value = self.dynamodb
        fake_boto3.client.side_effect = lambda service: {
            "bedrock-runtime": self.bedrock,
            "s3": self.s3,
        }[service]

        module_name = "lambda_handler_under_test"
        spec = importlib.util.spec_from_file_location(module_name, HANDLER_PATH)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        self.handler = importlib.util.module_from_spec(spec)

        with (
            patch.dict(sys.modules, {"boto3": fake_boto3}),
            patch.dict(
                os.environ,
                {
                    "TABLE_NAME": "offline-test-table",
                    "DATA_BUCKET": "offline-test-bucket",
                },
            ),
        ):
            spec.loader.exec_module(self.handler)

        self.handler.logger = MagicMock(name="logger")
        fake_boto3.resource.assert_called_once_with("dynamodb")
        self.dynamodb.Table.assert_called_once_with("offline-test-table")
        fake_boto3.client.assert_any_call("bedrock-runtime")
        fake_boto3.client.assert_any_call("s3")

    def configure_successful_bedrock_response(self, output="Generated answer"):
        self.bedrock.invoke_model.return_value = {
            "body": io.BytesIO(
                json.dumps({"content": [{"text": output}]}).encode("utf-8")
            )
        }

    def assert_no_aws_requests(self):
        self.bedrock.invoke_model.assert_not_called()
        self.table.put_item.assert_not_called()
        self.s3.put_object.assert_not_called()

    def assert_error(self, response, status_code, message):
        self.assertEqual(response["statusCode"], status_code)
        self.assertEqual(json.loads(response["body"]), {"error": message})

    def assert_internal_server_error(self, response, raw_message=None):
        self.assert_error(response, 500, "Internal server error")
        if raw_message is not None:
            self.assertNotIn(raw_message, response["body"])

    def test_missing_or_empty_body_returns_400_without_aws_requests(self):
        cases = ({}, {"body": None}, {"body": {}}, {"body": "{}"})

        for event in cases:
            with self.subTest(event=event):
                response = self.handler.lambda_handler(event, None)
                self.assert_error(response, 400, "Missing required field: input")

        self.assert_no_aws_requests()

    def test_empty_whitespace_or_non_string_input_returns_400(self):
        for user_input in ("", " \t\n ", 123, None, ["value"]):
            with self.subTest(user_input=user_input):
                response = self.handler.lambda_handler(
                    {"body": {"input": user_input}}, None
                )
                self.assert_error(response, 400, "Input must be a non-empty string")

        self.assert_no_aws_requests()

    def test_input_over_500_characters_returns_400(self):
        response = self.handler.lambda_handler(
            {"body": {"input": "x" * 501}}, None
        )

        self.assert_error(response, 400, "Input exceeds 500 character limit")
        self.assert_no_aws_requests()

    def test_malformed_json_returns_500_without_aws_requests(self):
        response = self.handler.lambda_handler({"body": "{"}, None)

        self.assert_internal_server_error(response)
        self.assert_no_aws_requests()

    def test_dictionary_body_completes_request_and_persists_result(self):
        self.configure_successful_bedrock_response()
        fixed_datetime = MagicMock(name="datetime")
        fixed_datetime.now.return_value = datetime(
            2026, 8, 24, 12, 34, 56, tzinfo=timezone.utc
        )

        with (
            patch.object(self.handler.uuid, "uuid4", return_value="fixed-request-id"),
            patch.object(self.handler, "datetime", fixed_datetime),
        ):
            response = self.handler.lambda_handler(
                {"body": {"input": "Explain serverless architecture."}}, None
            )

        expected_item = {
            "request_id": "fixed-request-id",
            "input": "Explain serverless architecture.",
            "output": "Generated answer",
            "timestamp": "2026-08-24T12:34:56Z",
            "status": "COMPLETED",
        }
        self.assertEqual(response["statusCode"], 200)
        response_body = json.loads(response["body"])
        self.assertEqual(
            response_body,
            {
                "request_id": "fixed-request-id",
                "response": "Generated answer",
            },
        )
        self.assertNotIn("timestamp", response_body)
        fixed_datetime.now.assert_called_once_with(self.handler.timezone.utc)

        self.bedrock.invoke_model.assert_called_once()
        bedrock_call = self.bedrock.invoke_model.call_args
        self.assertEqual(
            bedrock_call.kwargs["modelId"],
            "global.anthropic.claude-haiku-4-5-20251001-v1:0",
        )
        self.assertEqual(
            json.loads(bedrock_call.kwargs["body"]),
            {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            "Respond clearly and concisely: "
                            "Explain serverless architecture."
                        ),
                    }
                ],
                "max_tokens": 100,
                "temperature": 0.7,
            },
        )
        self.table.put_item.assert_called_once_with(Item=expected_item)
        self.s3.put_object.assert_called_once_with(
            Bucket="offline-test-bucket",
            Key="requests/2026-08-24T12:34:56Z-fixed-request-id.json",
            Body=json.dumps(expected_item),
            ContentType="application/json",
        )

    def test_json_string_body_is_accepted(self):
        self.configure_successful_bedrock_response()

        with patch.object(
            self.handler.uuid, "uuid4", return_value="json-string-request-id"
        ):
            response = self.handler.lambda_handler(
                {"body": json.dumps({"input": "Hello"})}, None
            )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            json.loads(response["body"]),
            {
                "request_id": "json-string-request-id",
                "response": "Generated answer",
            },
        )
        self.bedrock.invoke_model.assert_called_once()
        self.table.put_item.assert_called_once()
        self.s3.put_object.assert_called_once()

    def test_exactly_500_characters_is_accepted(self):
        self.configure_successful_bedrock_response()

        with patch.object(
            self.handler.uuid, "uuid4", return_value="boundary-request-id"
        ):
            response = self.handler.lambda_handler(
                {"body": {"input": "x" * 500}}, None
            )

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            json.loads(response["body"]),
            {
                "request_id": "boundary-request-id",
                "response": "Generated answer",
            },
        )
        self.bedrock.invoke_model.assert_called_once()
        self.table.put_item.assert_called_once()
        self.s3.put_object.assert_called_once()

    def test_bedrock_exception_returns_500_without_persistence(self):
        self.bedrock.invoke_model.side_effect = RuntimeError("Bedrock unavailable")

        response = self.handler.lambda_handler(
            {"body": {"input": "Hello"}}, None
        )

        self.assert_internal_server_error(response, "Bedrock unavailable")
        self.handler.logger.exception.assert_called_once_with(
            "Error processing request"
        )
        self.table.put_item.assert_not_called()
        self.s3.put_object.assert_not_called()

    def test_incomplete_bedrock_response_returns_500_without_persistence(self):
        self.bedrock.invoke_model.return_value = {
            "body": io.BytesIO(json.dumps({"content": []}).encode("utf-8"))
        }

        response = self.handler.lambda_handler(
            {"body": {"input": "Hello"}}, None
        )

        self.assert_internal_server_error(response)
        self.table.put_item.assert_not_called()
        self.s3.put_object.assert_not_called()

    def test_dynamodb_exception_returns_500_without_s3_write(self):
        self.configure_successful_bedrock_response()
        self.table.put_item.side_effect = RuntimeError("DynamoDB unavailable")

        response = self.handler.lambda_handler(
            {"body": {"input": "Hello"}}, None
        )

        self.assert_internal_server_error(response, "DynamoDB unavailable")
        self.handler.logger.exception.assert_called_once_with(
            "Error processing request"
        )
        self.bedrock.invoke_model.assert_called_once()
        self.table.put_item.assert_called_once()
        self.s3.put_object.assert_not_called()

    def test_s3_exception_returns_500_after_dynamodb_write(self):
        self.configure_successful_bedrock_response()
        self.s3.put_object.side_effect = RuntimeError("S3 unavailable")

        response = self.handler.lambda_handler(
            {"body": {"input": "Hello"}}, None
        )

        self.assert_internal_server_error(response, "S3 unavailable")
        self.handler.logger.exception.assert_called_once_with(
            "Error processing request"
        )
        self.bedrock.invoke_model.assert_called_once()
        self.table.put_item.assert_called_once()
        self.s3.put_object.assert_called_once()


if __name__ == "__main__":
    unittest.main()
