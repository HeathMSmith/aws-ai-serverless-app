#!/usr/bin/env python3
"""Render sanitized GitHub job summaries from Terraform plan metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


MAX_RESOURCE_ACTIONS = 25
MAX_DISPLAY_LENGTH = 300
OUTCOMES = (
    "success",
    "failure",
    "cancelled",
    "skipped",
    "unavailable",
    "not-applicable",
)

COMPLETION_TOTALS_PATTERN = re.compile(
    r"Apply complete! Resources:\s*"
    r"(?P<added>\d+) added,\s*"
    r"(?P<changed>\d+) changed,\s*"
    r"(?P<destroyed>\d+) destroyed\."
)


class SummaryError(ValueError):
    """Raised when supplied Terraform summary data cannot be parsed safely."""


def _describe_action_sequence(actions: tuple[str, ...]) -> str:
    """Return a bounded, escaped description of Terraform action names."""
    description = json.dumps(actions, ensure_ascii=True, separators=(",", ":"))
    if len(description) <= MAX_DISPLAY_LENGTH:
        return description
    return f"{description[: MAX_DISPLAY_LENGTH - 1]}…"


@dataclass(frozen=True)
class ResourceAction:
    """A Terraform address paired with a fixed, non-sensitive action label."""

    address: str
    label: str


@dataclass(frozen=True)
class PlanSummary:
    """Sanitized managed-resource and data-source action information."""

    additions: int
    changes: int
    destructions: int
    replacements: int
    managed_actions: tuple[ResourceAction, ...]
    data_reads: tuple[ResourceAction, ...]
    has_unrendered_output_changes: bool = False

    @property
    def is_noop(self) -> bool:
        return (
            not self.managed_actions
            and not self.data_reads
            and not self.has_unrendered_output_changes
        )


@dataclass(frozen=True)
class ExecutionTotals:
    """Final totals reported by Terraform Apply, including destroy applies."""

    added: int
    changed: int
    destroyed: int


@dataclass(frozen=True)
class SummaryMetadata:
    """Workflow metadata safe to display after Markdown delimiting."""

    environment: str
    commit: str
    actor: str
    event: str
    run_url: str
    run_attempt: str
    plan_outcome: str
    execution_outcome: str = "not-applicable"
    cloudfront_invalidation_outcome: str = "not-applicable"


def parse_plan_json(plan_json: str) -> PlanSummary:
    """Parse Terraform plan JSON without retaining or returning raw values."""
    if not plan_json.strip():
        raise SummaryError("Terraform plan JSON is empty.")

    try:
        document = json.loads(plan_json)
    except json.JSONDecodeError as exc:
        raise SummaryError(
            "Terraform plan JSON is malformed "
            f"at line {exc.lineno}, column {exc.colno}."
        ) from exc

    if not isinstance(document, dict):
        raise SummaryError("Terraform plan JSON must contain a JSON object.")

    resource_changes = document.get("resource_changes", [])
    if not isinstance(resource_changes, list):
        raise SummaryError("Terraform plan resource_changes must be a list.")

    additions = 0
    changes = 0
    destructions = 0
    replacements = 0
    managed_actions = []
    data_reads = []

    for index, resource_change in enumerate(resource_changes):
        if not isinstance(resource_change, dict):
            raise SummaryError(
                f"Terraform resource change {index} must be a JSON object."
            )

        address = resource_change.get("address")
        mode = resource_change.get("mode")
        change = resource_change.get("change")
        if not isinstance(address, str) or not address:
            raise SummaryError(
                f"Terraform resource change {index} has no valid address."
            )
        if not isinstance(change, dict):
            raise SummaryError(
                f"Terraform resource change {index} has no valid change object."
            )

        actions = change.get("actions")
        if not isinstance(actions, list) or not all(
            isinstance(action, str) for action in actions
        ):
            raise SummaryError(
                f"Terraform resource change {index} has no valid actions list."
            )

        action_tuple = tuple(actions)
        if mode == "data":
            if action_tuple == ("read",):
                data_reads.append(ResourceAction(address, "Read during apply"))
            elif action_tuple != ("no-op",):
                raise SummaryError(
                    "Unsupported data-source action sequence "
                    f"{_describe_action_sequence(action_tuple)} at resource "
                    f"change {index}."
                )
            continue

        if mode != "managed":
            continue
        if action_tuple == ("no-op",):
            continue
        if action_tuple == ("create",):
            additions += 1
            label = "Create"
        elif action_tuple == ("update",):
            changes += 1
            label = "Update in place"
        elif action_tuple == ("delete",):
            destructions += 1
            label = "Destroy"
        elif action_tuple in (("delete", "create"), ("create", "delete")):
            additions += 1
            destructions += 1
            replacements += 1
            label = "Replace"
        else:
            raise SummaryError(
                "Unsupported managed-resource action sequence "
                f"{_describe_action_sequence(action_tuple)} at resource "
                f"change {index}."
            )

        managed_actions.append(ResourceAction(address, label))

    output_changes = document.get("output_changes", {})
    if output_changes is None:
        output_changes = {}
    if not isinstance(output_changes, dict):
        raise SummaryError("Terraform plan output_changes must be an object.")

    has_unrendered_output_changes = False
    for output_change in output_changes.values():
        if not isinstance(output_change, dict):
            raise SummaryError("Terraform output change must be a JSON object.")
        output_actions = output_change.get("actions", [])
        if not isinstance(output_actions, list) or not all(
            isinstance(action, str) for action in output_actions
        ):
            raise SummaryError("Terraform output change has no valid actions list.")
        if tuple(output_actions) != ("no-op",):
            has_unrendered_output_changes = True

    return PlanSummary(
        additions=additions,
        changes=changes,
        destructions=destructions,
        replacements=replacements,
        managed_actions=tuple(managed_actions),
        data_reads=tuple(data_reads),
        has_unrendered_output_changes=has_unrendered_output_changes,
    )


def parse_execution_totals(execution_output: str) -> ExecutionTotals | None:
    """Return the final Terraform Apply totals without exposing other output."""
    matches = list(COMPLETION_TOTALS_PATTERN.finditer(execution_output))
    if not matches:
        return None

    match = matches[-1]
    return ExecutionTotals(
        added=int(match.group("added")),
        changed=int(match.group("changed")),
        destroyed=int(match.group("destroyed")),
    )


def _single_line(value: str) -> str:
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= MAX_DISPLAY_LENGTH:
        return collapsed
    return f"{collapsed[: MAX_DISPLAY_LENGTH - 1]}…"


def markdown_code(value: str) -> str:
    """Safely delimit an untrusted value as a single-line Markdown code span."""
    safe_value = _single_line(value)
    longest_run = max(
        (len(match.group(0)) for match in re.finditer(r"`+", safe_value)),
        default=0,
    )
    fence = "`" * max(1, longest_run + 1)
    padding = " " if safe_value.startswith("`") or safe_value.endswith("`") else ""
    return f"{fence}{padding}{safe_value}{padding}{fence}"


def _outcome_label(outcome: str) -> str:
    labels = {
        "success": "Succeeded",
        "failure": "Failed",
        "cancelled": "Cancelled",
        "skipped": "Skipped",
        "unavailable": "Unavailable",
        "not-applicable": "Not applicable",
    }
    return labels.get(outcome, _single_line(outcome))


def _render_metadata(metadata: SummaryMetadata, operation: str) -> list[str]:
    lines = [
        f"- **Environment:** {markdown_code(metadata.environment)}",
        f"- **Commit:** {markdown_code(metadata.commit)}",
        f"- **Actor:** {markdown_code(metadata.actor)}",
        f"- **Event:** {markdown_code(metadata.event)}",
        f"- **Run:** {markdown_code(metadata.run_url)}",
        f"- **Run attempt:** {markdown_code(metadata.run_attempt)}",
        f"- **Plan outcome:** {_outcome_label(metadata.plan_outcome)}",
    ]
    if operation in ("apply", "destroy"):
        lines.append(
            f"- **Execution outcome:** "
            f"{_outcome_label(metadata.execution_outcome)}"
        )
    if operation == "apply":
        lines.append(
            f"- **CloudFront invalidation:** "
            f"{_outcome_label(metadata.cloudfront_invalidation_outcome)}"
        )
    return lines


def _render_plan_data(
    plan: PlanSummary | None,
    plan_outcome: str,
    max_actions: int,
) -> list[str]:
    lines = ["### Planned resource changes", ""]
    if plan_outcome != "success":
        lines.extend(
            [
                "Terraform planning did not complete successfully.",
                "See the Terraform workflow logs for diagnostic details.",
            ]
        )
        return lines
    if plan is None:
        lines.extend(
            [
                "Structured Terraform plan data was unavailable.",
                "See the Terraform workflow logs for diagnostic details.",
            ]
        )
        return lines

    lines.extend(
        [
            "| Add | Change | Destroy | Replace | Data reads |",
            "| ---: | ---: | ---: | ---: | ---: |",
            (
                f"| {plan.additions} | {plan.changes} | {plan.destructions} | "
                f"{plan.replacements} | {len(plan.data_reads)} |"
            ),
            "",
        ]
    )

    if plan.is_noop:
        lines.append(
            "No managed resource changes are planned. "
            "Terraform reports that infrastructure matches configuration."
        )
        return lines

    if not plan.managed_actions:
        lines.append("No managed resource changes are planned.")
        lines.append("")
    if plan.has_unrendered_output_changes:
        lines.append(
            "Terraform reports output-only changes; output values are intentionally "
            "not rendered."
        )
        lines.append("")

    categorized_actions = [
        ("Managed resource actions", action) for action in plan.managed_actions
    ] + [("Data-source reads", action) for action in plan.data_reads]
    visible_actions = categorized_actions[:max_actions]
    current_category = None
    for category, action in visible_actions:
        if category != current_category:
            if current_category is not None:
                lines.append("")
            lines.extend([f"#### {category}", ""])
            current_category = category
        lines.append(f"- {markdown_code(action.address)} — {action.label}")

    omitted_count = len(categorized_actions) - len(visible_actions)
    if omitted_count:
        lines.extend(
            [
                "",
                f"_{omitted_count} additional resource actions omitted._",
            ]
        )
    return lines


def _render_execution_data(
    operation: str,
    outcome: str,
    totals: ExecutionTotals | None,
) -> list[str]:
    noun = "Apply" if operation == "apply" else "Destroy"
    lines = [f"### Terraform {noun} execution", ""]
    if outcome != "success":
        lines.extend(
            [
                f"Terraform {noun} did not complete successfully.",
                "See the Terraform workflow logs for diagnostic details.",
            ]
        )
        return lines
    if totals is None:
        lines.extend(
            [
                f"Terraform {noun} completed successfully, but completion totals "
                "were unavailable.",
                "See the Terraform workflow logs for additional details.",
            ]
        )
        return lines

    lines.extend(
        [
            "| Added | Changed | Destroyed |",
            "| ---: | ---: | ---: |",
            f"| {totals.added} | {totals.changed} | {totals.destroyed} |",
        ]
    )
    return lines


def render_markdown(
    operation: str,
    metadata: SummaryMetadata,
    plan: PlanSummary | None,
    execution_totals: ExecutionTotals | None = None,
    *,
    max_actions: int = MAX_RESOURCE_ACTIONS,
) -> str:
    """Render a bounded summary containing metadata, counts, and addresses only."""
    if operation not in ("plan", "apply", "destroy"):
        raise SummaryError(f"Unsupported operation: {operation}")
    if max_actions <= 0:
        raise SummaryError("Resource action limit must be greater than zero.")

    title = {
        "plan": "Terraform Plan Summary",
        "apply": "Terraform Apply Summary",
        "destroy": "Terraform Destroy Summary",
    }[operation]
    lines = [f"## {title}", ""]
    lines.extend(_render_metadata(metadata, operation))
    lines.append("")
    lines.extend(_render_plan_data(plan, metadata.plan_outcome, max_actions))
    if operation in ("apply", "destroy"):
        lines.extend([""])
        lines.extend(
            _render_execution_data(
                operation,
                metadata.execution_outcome,
                execution_totals,
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Render a sanitized Terraform workflow summary. Terraform plan JSON "
            "is read from standard input when supplied."
        )
    )
    parser.add_argument(
        "--operation",
        required=True,
        choices=("plan", "apply", "destroy"),
    )
    parser.add_argument("--environment", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--run-attempt", required=True)
    parser.add_argument("--plan-outcome", required=True, choices=OUTCOMES)
    parser.add_argument(
        "--execution-outcome",
        default="not-applicable",
        choices=OUTCOMES,
    )
    parser.add_argument(
        "--cloudfront-invalidation-outcome",
        default="not-applicable",
        choices=OUTCOMES,
    )
    parser.add_argument(
        "--execution-output",
        type=Path,
        help="Optional Terraform Apply output file used only to extract final totals.",
    )
    return parser.parse_args(argv)


def main(
    argv=None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    args = parse_args(argv)
    input_stream = stdin or sys.stdin
    output_stream = stdout or sys.stdout
    error_stream = stderr or sys.stderr

    try:
        supplied_plan_json = input_stream.read()
        plan = (
            parse_plan_json(supplied_plan_json)
            if supplied_plan_json.strip()
            else None
        )

        execution_totals = None
        if args.execution_output is not None:
            try:
                execution_output = args.execution_output.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise SummaryError(
                    "Unable to read Terraform execution output."
                ) from exc
            execution_totals = parse_execution_totals(execution_output)

        metadata = SummaryMetadata(
            environment=args.environment,
            commit=args.commit,
            actor=args.actor,
            event=args.event,
            run_url=args.run_url,
            run_attempt=args.run_attempt,
            plan_outcome=args.plan_outcome,
            execution_outcome=args.execution_outcome,
            cloudfront_invalidation_outcome=(
                args.cloudfront_invalidation_outcome
            ),
        )
        markdown = render_markdown(
            args.operation,
            metadata,
            plan,
            execution_totals,
        )
    except SummaryError as exc:
        print(f"error: {exc}", file=error_stream)
        return 1

    print(markdown, end="", file=output_stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
