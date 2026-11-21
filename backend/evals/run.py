"""Eval runner entry point: `uv run poe eval <suite>` (P1-4)."""

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any


class _NoopRunContext:
    """Minimal RunContext stand-in for offline/eval runs without DB writes."""

    async def step(self, *args: Any, **kwargs: Any) -> None:
        return None


def _load_cases(dataset_path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _write_report(report_path: Path, report: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


async def run_suite(suite_name: str) -> dict[str, Any]:
    """Load `evals.suites.<suite_name>`, execute all JSONL cases, and return summary."""
    suite = importlib.import_module(f"evals.suites.{suite_name}")
    cases = await asyncio.to_thread(_load_cases, Path(suite.DATASET))
    ctx: dict[str, Any] = {"run": _NoopRunContext()}
    results = [await suite.run_case(case, ctx) for case in cases]
    summary = suite.summarize(results)
    report = {"suite": suite_name, "summary": summary, "results": results}

    report_path = Path(__file__).parent / "results" / f"{suite_name}.json"
    await asyncio.to_thread(_write_report, report_path, report)
    return report


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: python -m evals.run <suite> (e.g. icp)", file=sys.stderr)
        return 1
    suite_name = argv[0]
    report = asyncio.run(run_suite(suite_name))
    print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
    return 0 if report["summary"].get("failed", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
