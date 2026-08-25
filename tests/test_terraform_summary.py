import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import render_terraform_summary as summary


def resource_change(address, actions, *, mode="managed", **extra):
    change = {"actions": list(actions)}
    change.update(extra)
    return {
        "address": address,
        "mode": mode,
        "type": "test_resource",
        "name": "example",
        "change": change,
    }


def plan_json(*resource_changes, output_changes=None, **extra):
    document = {
        "format_version": "1.2",
        "resource_changes": list(resource_changes),
        "output_changes": output_changes or {},
    }
    document.update(extra)
    return json.dumps(document)


def metadata(**overrides):
    values = {
        "environment": "dev",
        "commit": "abc123",
        "actor": "test-actor",
        "event": "workflow_dispatch",
        "run_url": "https://example.test/actions/runs/1",
        "run_attempt": "1",
        "plan_outcome": "success",
        "execution_outcome": "not-applicable",
        "cloudfront_invalidation_outcome": "not-applicable",
    }
    values.update(overrides)
    return summary.SummaryMetadata(**values)


class TerraformPlanParsingTests(unittest.TestCase):
    def test_noop_plan(self):
        parsed = summary.parse_plan_json(
            plan_json(resource_change("test_resource.noop", ["no-op"]))
        )

        self.assertTrue(parsed.is_noop)
        self.assertEqual(parsed.additions, 0)
        self.assertEqual(parsed.changes, 0)
        self.assertEqual(parsed.destructions, 0)
        self.assertEqual(parsed.replacements, 0)
        self.assertEqual(parsed.managed_actions, ())

    def test_create_update_and_destroy_counts(self):
        parsed = summary.parse_plan_json(
            plan_json(
                resource_change("test_resource.create", ["create"]),
                resource_change("test_resource.update", ["update"]),
                resource_change("test_resource.destroy", ["delete"]),
            )
        )

        self.assertEqual(parsed.additions, 1)
        self.assertEqual(parsed.changes, 1)
        self.assertEqual(parsed.destructions, 1)
        self.assertEqual(parsed.replacements, 0)

    def test_both_replacement_action_orderings(self):
        parsed = summary.parse_plan_json(
            plan_json(
                resource_change("test_resource.destroy_first", ["delete", "create"]),
                resource_change("test_resource.create_first", ["create", "delete"]),
            )
        )

        self.assertEqual(parsed.additions, 2)
        self.assertEqual(parsed.changes, 0)
        self.assertEqual(parsed.destructions, 2)
        self.assertEqual(parsed.replacements, 2)

    def test_data_source_reads_are_reported_separately(self):
        parsed = summary.parse_plan_json(
            plan_json(
                resource_change("data.test.current", ["read"], mode="data"),
                resource_change("test_resource.create", ["create"]),
            )
        )

        self.assertEqual(len(parsed.managed_actions), 1)
        self.assertEqual(
            parsed.data_reads,
            (summary.ResourceAction("data.test.current", "Read during apply"),),
        )

    def test_managed_noop_entries_are_ignored(self):
        parsed = summary.parse_plan_json(
            plan_json(
                resource_change("test_resource.noop", ["no-op"]),
                resource_change("test_resource.update", ["update"]),
            )
        )

        self.assertEqual(
            parsed.managed_actions,
            (summary.ResourceAction("test_resource.update", "Update in place"),),
        )

    def test_resource_action_labels(self):
        parsed = summary.parse_plan_json(
            plan_json(
                resource_change("test_resource.create", ["create"]),
                resource_change("test_resource.update", ["update"]),
                resource_change("test_resource.destroy", ["delete"]),
                resource_change("test_resource.replace", ["delete", "create"]),
            )
        )

        self.assertEqual(
            [action.label for action in parsed.managed_actions],
            ["Create", "Update in place", "Destroy", "Replace"],
        )

    def test_output_only_plan_changes_are_detected_without_rendering_values(self):
        secret_output = "do-not-render-output-value"
        parsed = summary.parse_plan_json(
            plan_json(
                output_changes={
                    "sensitive_output": {
                        "actions": ["update"],
                        "before": secret_output,
                        "after": "replacement-output-value",
                    }
                }
            )
        )

        rendered = summary.render_markdown("plan", metadata(), parsed)

        self.assertFalse(parsed.is_noop)
        self.assertEqual(parsed.additions, 0)
        self.assertEqual(parsed.changes, 0)
        self.assertEqual(parsed.destructions, 0)
        self.assertIn("output-only changes", rendered)
        self.assertNotIn("sensitive_output", rendered)
        self.assertNotIn(secret_output, rendered)
        self.assertNotIn("replacement-output-value", rendered)


class TerraformExecutionParsingTests(unittest.TestCase):
    def test_apply_completion_totals(self):
        totals = summary.parse_execution_totals(
            "Apply complete! Resources: 0 added, 1 changed, 0 destroyed.\n"
        )

        self.assertEqual(totals, summary.ExecutionTotals(0, 1, 0))

    def test_destroy_completion_totals(self):
        totals = summary.parse_execution_totals(
            "Apply complete! Resources: 0 added, 0 changed, 33 destroyed.\n"
        )

        self.assertEqual(totals, summary.ExecutionTotals(0, 0, 33))

    def test_missing_completion_totals(self):
        self.assertIsNone(
            summary.parse_execution_totals("Terraform execution failed before completion")
        )


class TerraformMarkdownRenderingTests(unittest.TestCase):
    def test_successful_plan_markdown(self):
        parsed = summary.parse_plan_json(
            plan_json(resource_change("test_resource.noop", ["no-op"]))
        )

        rendered = summary.render_markdown("plan", metadata(), parsed)

        self.assertIn("## Terraform Plan Summary", rendered)
        self.assertIn("| 0 | 0 | 0 | 0 | 0 |", rendered)
        self.assertIn("infrastructure matches configuration", rendered)
        self.assertIn("**Plan outcome:** Succeeded", rendered)

    def test_successful_apply_markdown(self):
        parsed = summary.parse_plan_json(
            plan_json(resource_change("test_resource.update", ["update"]))
        )
        rendered = summary.render_markdown(
            "apply",
            metadata(
                execution_outcome="success",
                cloudfront_invalidation_outcome="success",
            ),
            parsed,
            summary.ExecutionTotals(0, 1, 0),
        )

        self.assertIn("## Terraform Apply Summary", rendered)
        self.assertIn("**Execution outcome:** Succeeded", rendered)
        self.assertIn("**CloudFront invalidation:** Succeeded", rendered)
        self.assertIn("| 0 | 1 | 0 |", rendered)

    def test_successful_destroy_markdown(self):
        parsed = summary.parse_plan_json(
            plan_json(resource_change("test_resource.destroy", ["delete"]))
        )
        rendered = summary.render_markdown(
            "destroy",
            metadata(execution_outcome="success"),
            parsed,
            summary.ExecutionTotals(0, 0, 1),
        )

        self.assertIn("## Terraform Destroy Summary", rendered)
        self.assertIn("### Terraform Destroy execution", rendered)
        self.assertIn("| 0 | 0 | 1 |", rendered)
        self.assertNotIn("CloudFront", rendered)

    def test_successful_execution_with_missing_totals(self):
        parsed = summary.parse_plan_json(plan_json())
        rendered = summary.render_markdown(
            "apply",
            metadata(execution_outcome="success"),
            parsed,
        )

        self.assertIn("**Execution outcome:** Succeeded", rendered)
        self.assertIn("completion totals were unavailable", rendered)
        self.assertIn("workflow logs", rendered)

    def test_failed_operation_markdown(self):
        rendered = summary.render_markdown(
            "apply",
            metadata(
                plan_outcome="failure",
                execution_outcome="skipped",
                cloudfront_invalidation_outcome="skipped",
            ),
            None,
        )

        self.assertIn("**Plan outcome:** Failed", rendered)
        self.assertIn("**Execution outcome:** Skipped", rendered)
        self.assertIn("workflow logs", rendered)
        self.assertNotIn("AccessDenied: secret policy value", rendered)

    def test_cancelled_outcomes_are_rendered(self):
        rendered = summary.render_markdown(
            "destroy",
            metadata(
                plan_outcome="cancelled",
                execution_outcome="cancelled",
            ),
            None,
        )

        self.assertIn("**Plan outcome:** Cancelled", rendered)
        self.assertIn("**Execution outcome:** Cancelled", rendered)
        self.assertIn("workflow logs", rendered)

    def test_missing_plan_json_is_rendered_as_unavailable(self):
        rendered = summary.render_markdown("plan", metadata(), None)

        self.assertIn("Structured Terraform plan data was unavailable", rendered)
        self.assertIn("workflow logs", rendered)

    def test_raw_plan_attributes_values_and_errors_are_not_rendered(self):
        raw_secret = "do-not-render-this-secret"
        parsed = summary.parse_plan_json(
            plan_json(
                resource_change(
                    "test_resource.safe_address",
                    ["update"],
                    before={"token": raw_secret},
                    after={"token": "new-secret-value"},
                ),
                planned_values={"outputs": {"secret": {"value": raw_secret}}},
                resource_drift=[{"change": {"before": raw_secret}}],
            )
        )
        execution_output = f"Error: {raw_secret}\n"
        rendered = summary.render_markdown(
            "apply",
            metadata(execution_outcome="failure"),
            parsed,
            summary.parse_execution_totals(execution_output),
        )

        self.assertIn("test_resource.safe_address", rendered)
        self.assertNotIn(raw_secret, rendered)
        self.assertNotIn("new-secret-value", rendered)
        self.assertNotIn("Error:", rendered)

    def test_markdown_safe_metadata_and_resource_presentation(self):
        unsafe_address = 'test_resource.example["a`b\n## forged heading"]'
        parsed = summary.parse_plan_json(
            plan_json(resource_change(unsafe_address, ["create"]))
        )
        rendered = summary.render_markdown(
            "plan",
            metadata(actor="actor`name\n## forged actor heading"),
            parsed,
        )

        self.assertNotIn("\n## forged heading", rendered)
        self.assertNotIn("\n## forged actor heading", rendered)
        self.assertIn("``actor`name ## forged actor heading``", rendered)
        self.assertIn(
            '``test_resource.example["a`b ## forged heading"]`` — Create',
            rendered,
        )

    def test_resource_list_is_truncated(self):
        extra_actions = 3
        parsed = summary.parse_plan_json(
            plan_json(
                *(
                    resource_change(f"test_resource.item_{index}", ["create"])
                    for index in range(summary.MAX_RESOURCE_ACTIONS + extra_actions)
                )
            )
        )

        rendered = summary.render_markdown("plan", metadata(), parsed)

        self.assertEqual(rendered.count(" — Create"), summary.MAX_RESOURCE_ACTIONS)
        self.assertIn(
            f"_{extra_actions} additional resource actions omitted._",
            rendered,
        )


class TerraformSummaryCliTests(unittest.TestCase):
    def base_arguments(self):
        return [
            "--operation",
            "plan",
            "--environment",
            "dev",
            "--commit",
            "abc123",
            "--actor",
            "test-actor",
            "--event",
            "workflow_dispatch",
            "--run-url",
            "https://example.test/actions/runs/1",
            "--run-attempt",
            "1",
            "--plan-outcome",
            "success",
        ]

    def test_malformed_plan_json_returns_nonzero_without_stdout(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        result = summary.main(
            self.base_arguments(),
            stdin=io.StringIO("{"),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(result, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Terraform plan JSON is malformed", stderr.getvalue())

    def test_successful_cli_execution_reads_plan_json_from_stdin(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        result = summary.main(
            self.base_arguments(),
            stdin=io.StringIO(plan_json()),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(result, 0)
        self.assertIn("## Terraform Plan Summary", stdout.getvalue())
        self.assertIn("infrastructure matches configuration", stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")

    def test_unsupported_action_error_does_not_expose_malicious_address(self):
        malicious_address = "test_resource.example\n::error::forged-log-command"
        stdout = io.StringIO()
        stderr = io.StringIO()
        unsupported_plan = plan_json(
            resource_change(malicious_address, ["create", "update"])
        )

        result = summary.main(
            self.base_arguments(),
            stdin=io.StringIO(unsupported_plan),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(result, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("Unsupported managed-resource action sequence", stderr.getvalue())
        self.assertIn('["create","update"]', stderr.getvalue())
        self.assertIn("resource change 0", stderr.getvalue())
        self.assertNotIn(malicious_address, stderr.getvalue())
        self.assertNotIn("forged-log-command", stderr.getvalue())

    def test_unreadable_execution_output_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing_path = Path(temporary_directory) / "missing.txt"
            stdout = io.StringIO()
            stderr = io.StringIO()
            arguments = self.base_arguments() + [
                "--execution-output",
                str(missing_path),
            ]

            result = summary.main(
                arguments,
                stdin=io.StringIO(plan_json()),
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(result, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "Unable to read Terraform execution output",
            stderr.getvalue(),
        )

    def test_invalid_utf8_execution_output_returns_sanitized_error(self):
        raw_contents = b"\xffsecret-file-contents"
        with tempfile.TemporaryDirectory() as temporary_directory:
            execution_output = Path(temporary_directory) / "apply.txt"
            execution_output.write_bytes(raw_contents)
            stdout = io.StringIO()
            stderr = io.StringIO()
            arguments = self.base_arguments() + [
                "--execution-output",
                str(execution_output),
            ]

            result = summary.main(
                arguments,
                stdin=io.StringIO(plan_json()),
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(result, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            stderr.getvalue(),
            "error: Unable to read Terraform execution output.\n",
        )
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertNotIn("secret-file-contents", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
