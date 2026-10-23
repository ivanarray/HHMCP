from pydantic import BaseModel


class VacancyCard(BaseModel):
    id: int
    url: str
    title: str
    company: str | None
    company_id: int | None
    company_rating: float | None
    salary_from: int | None
    salary_to: int | None
    currency: str | None
    salary_gross: bool | None
    area: str | None
    address: str | None
    experience: str | None
    employment_form: str | None
    work_formats: list[str]
    schedule: list[str]
    published_at: str | None
    responses_count: int | None
    has_test: bool | None  # None: not shown on the vacancy page
    letter_required: bool | None


class VacancyDetails(VacancyCard):
    description: str
    key_skills: list[str]
    archived: bool
    applied: bool | None  # None: applied list not synced (no login)


class SearchResult(BaseModel):
    total: int
    page: int
    pages: int
    applied_filtered: int
    applied_filter: str  # "on" | "off" | "unavailable: run login"
    items: list[VacancyCard]
