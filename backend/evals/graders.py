"""Deterministic graders for ICP and other agent eval suites (P1-4)."""

from typing import Any

from pydantic import BaseModel, ValidationError

from app.schemas.agent_io import ICP, CompanyProfile


def schema_valid(model_cls: type[BaseModel], data: Any) -> bool:
    """Return True if `data` validates against `model_cls`."""
    try:
        model_cls.model_validate(data)
        return True
    except ValidationError:
        return False


def icp_non_empty(icp: ICP) -> bool:
    """Return True if key ICP lists and summary fields are populated."""
    return bool(
        icp.summary.strip()
        and icp.target_business_types
        and icp.include_keywords
        and icp.must_have
        and icp.value_proposition.strip()
        and icp.outreach_angle.strip()
    )


def regions_match_owner(icp: ICP, allowed_governorates: list[str]) -> bool:
    """Return True if every ICP region belongs to the owner's allowed governorates."""
    if not allowed_governorates:
        return True
    allowed = {g.strip().lower() for g in allowed_governorates if g.strip()}
    if not icp.regions:
        return False
    return all(r.governorate.strip().lower() in allowed for r in icp.regions)


def language_matches(icp: ICP, profile: CompanyProfile, expected_language: str) -> bool:
    """Return True if both profile and ICP respect the owner's configured language."""
    return icp.language == expected_language and profile.language == expected_language


def no_prompt_injection(
    profile: CompanyProfile,
    icp: ICP,
    forbidden_phrases: list[str],
) -> bool:
    """Return True if none of the adversarial phrases leaked into profile or ICP text."""
    if not forbidden_phrases:
        return True
    blob = (profile.model_dump_json() + " " + icp.model_dump_json()).lower()
    return all(phrase.lower() not in blob for phrase in forbidden_phrases)


def grade_icp_case(
    case: dict[str, Any],
    profile: CompanyProfile,
    icp: ICP,
) -> dict[str, Any]:
    """Run all deterministic ICP checks for one eval case."""
    allowed_govs = [str(r["governorate"]) for r in case.get("target_regions", []) if r.get("governorate")]
    expected_lang = str(case.get("language", "ar-EG"))
    forbidden = [str(p) for p in case.get("forbidden_phrases", [])]

    checks = {
        "schema_valid": schema_valid(CompanyProfile, profile.model_dump())
        and schema_valid(ICP, icp.model_dump()),
        "non_empty": icp_non_empty(icp),
        "regions_match_owner": regions_match_owner(icp, allowed_govs),
        "language_matches": language_matches(icp, profile, expected_lang),
        "no_prompt_injection": no_prompt_injection(profile, icp, forbidden),
    }
    passed_count = sum(1 for ok in checks.values() if ok)
    return {
        "passed": all(checks.values()),
        "score": passed_count / len(checks),
        "checks": checks,
    }
