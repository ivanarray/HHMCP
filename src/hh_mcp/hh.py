import math
from typing import Literal

from markdownify import markdownify

from hh_mcp.models import SearchResult, VacancyCard, VacancyDetails

Experience = Literal["noExperience", "between1And3", "between3And6", "moreThan6"]
EmploymentForm = Literal["FULL", "PART", "PROJECT", "FLY_IN_FLY_OUT"]
WorkFormat = Literal["ON_SITE", "REMOTE", "HYBRID", "FIELD_WORK"]
OrderBy = Literal["relevance", "publication_time", "salary_desc", "salary_asc"]
SearchField = Literal["name", "company_name", "description"]
MAX_RESULTS = 2000  # hh.ru does not page beyond 2000 results


def search_params(
    text: str, area: int, salary: int | None, only_with_salary: bool, experience: list[Experience],
    employment_form: list[EmploymentForm], work_format: list[WorkFormat], period_days: int | None,
    order_by: OrderBy, page: int, per_page: int, search_field: list[SearchField] = [],
) -> list[tuple[str, str | int]]:
    """Query string of hh.ru/search/vacancy; repeated keys for multi-select filters."""
    params = [("text", text), ("area", area), ("order_by", order_by), ("page", page), ("items_on_page", per_page)]
    params += [("experience", v) for v in experience]
    params += [("employment_form", v) for v in employment_form]
    params += [("work_format", v) for v in work_format]
    params += [("search_field", v) for v in search_field]
    if salary:
        params.append(("salary", salary))
    if only_with_salary:
        params.append(("only_with_salary", "true"))
    if period_days:
        params.append(("search_period", period_days))
    return params


def _flat(value) -> list[str]:
    """Search cards nest lists as [{"xElement": [...]}], vacancy pages give plain lists."""
    out = []
    for item in value or []:
        if isinstance(item, dict):  # may be empty: [{}]
            for values in item.values():
                out += values
        else:
            out.append(item)
    return out


def _card_fields(v: dict, company: dict, area: dict) -> dict:
    pay = v.get("compensation") or {}
    rating = (company.get("employerReviews") or {}).get("totalRating")
    return dict(
        id=v["vacancyId"],
        url=f"https://hh.ru/vacancy/{v['vacancyId']}",
        title=v["name"],
        company=company.get("visibleName") or company.get("name"),
        company_id=company.get("id"),
        company_rating=float(rating) if rating else None,
        salary_from=pay.get("from"),
        salary_to=pay.get("to"),
        currency=pay.get("currencyCode"),
        salary_gross=pay.get("gross"),
        area=area.get("name"),
        address=(v.get("address") or {}).get("displayName"),
        experience=v.get("workExperience"),
        employment_form=v.get("employmentForm"),
        work_formats=_flat(v.get("workFormats")),
        schedule=_flat(v.get("workScheduleByDays")),
    )


def parse_search(state: dict, applied: set[int] | None, exclude_applied: bool) -> SearchResult:
    r = state["vacancySearchResult"]
    per_page = r["criteria"]["items_on_page"]
    items = [
        VacancyCard(
            **_card_fields(v, v.get("company") or {}, v.get("area") or {}),
            published_at=(v.get("publicationTime") or {}).get("$"),
            responses_count=v.get("responsesCount"),
            has_test=bool(v.get("userTestPresent")),
            letter_required=bool(v.get("@responseLetterRequired")),
        )
        for v in r["vacancies"]
    ]
    kept = [c for c in items if c.id not in applied] if exclude_applied and applied is not None else items
    return SearchResult(
        total=r["totalResults"],
        page=r["criteria"]["page"],
        pages=math.ceil(min(r["totalResults"], MAX_RESULTS) / per_page),
        applied_filtered=len(items) - len(kept),
        applied_filter="off" if not exclude_applied else "on" if applied is not None else "unavailable: run login",
        items=kept,
    )


def parse_vacancy(state: dict, applied: set[int] | None) -> VacancyDetails:
    v = state["vacancyView"]["vacancyFull"]["vacancy"]
    return VacancyDetails(
        **_card_fields(v, v.get("company") or {}, v.get("area") or {}),
        published_at=v.get("publicationTimeIso"),
        responses_count=None,
        has_test=None,
        letter_required=None,
        description=markdownify(v.get("description") or "").strip(),
        key_skills=v.get("keySkills") or [],
        archived=bool((v.get("status") or {}).get("archived")),
        applied=None if applied is None else v["vacancyId"] in applied,
    )
