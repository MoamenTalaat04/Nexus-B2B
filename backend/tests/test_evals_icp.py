"""Tests for P1-4 ICP eval suite and graders."""

from evals.run import run_suite


async def test_icp_eval_suite_passes_all_cases() -> None:
    report = await run_suite("icp")
    summary = report["summary"]
    assert summary["total"] == 5
    assert summary["passed"] == 5
    assert summary["failed"] == 0
    assert summary["pass_rate"] == 1.0
