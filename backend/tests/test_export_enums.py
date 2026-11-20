"""P0-2: the TS enum mirror generator is deterministic and covers every StrEnum."""

from pathlib import Path

from app.models import enums
from scripts import export_enums


def test_every_enum_and_value_is_exported() -> None:
    out = export_enums.render()
    for cls in export_enums.enum_classes():
        assert f"export type {cls.__name__} = " in out
        for member in cls:
            assert f'"{member.value}"' in out
    assert "INTENT_TO_STATUS" in out
    assert {c.__name__ for c in export_enums.enum_classes()} >= {"LeadStatus", "MessageStatus", "ReplyIntent"}
    assert enums.LeadStatus.OPTED_OUT.value in out


def test_output_is_deterministic(tmp_path: Path) -> None:
    target = tmp_path / "types.ts"
    assert export_enums.main(["--out", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == export_enums.render()
    assert export_enums.main(["--check", str(target)]) == 0
    target.write_text("stale", encoding="utf-8")
    assert export_enums.main(["--check", str(target)]) == 1
