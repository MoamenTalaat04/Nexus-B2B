"""Eval runner entry point: `uv run poe eval <suite>`. The harness is built in P1-4."""

import sys


def main(argv: list[str]) -> int:
    suite = argv[0] if argv else "<none>"
    print(f"eval harness not implemented yet (P1-4). Requested suite: {suite}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
