import asyncio
import json
import logging
import sys
from typing import Annotated, Literal

from mcp.server import MCPServer
from pydantic import Field

from hh_mcp import account, hh
from hh_mcp.client import SearchClient
from hh_mcp.models import SearchResult, VacancyDetails

logging.basicConfig(level=logging.INFO, stream=sys.stderr)

mcp = MCPServer(
    "hh",
    instructions=(
        "Search vacancies on hh.ru. search_vacancies returns short cards; call get_vacancy for the full text. "
        "Searches are anonymous. Vacancies the user already applied to are filtered out once login has been done."
    ),
)
_client: SearchClient | None = None


def client() -> SearchClient:
    global _client
    _client = _client or SearchClient()
    return _client


@mcp.tool()
async def search_vacancies(
    text: Annotated[str, Field(description="Search query, hh.ru syntax works (AND, OR, NOT, quotes)")],
    search_field: Annotated[list[hh.SearchField], Field(
        description="Where the text must match; ['name'] is the strictest (title only). Empty: title, company and description"
    )] = [],
    area: Annotated[int, Field(description="Region id: 113 Russia, 1 Moscow, 2 Saint Petersburg, 3 Yekaterinburg, "
                                           "4 Novosibirsk, 88 Kazan, 66 Nizhny Novgorod, 16 Belarus, 40 Kazakhstan")] = 113,
    salary: Annotated[int | None, Field(description="Desired monthly salary in RUB")] = None,
    only_with_salary: bool = False,
    experience: list[hh.Experience] = [],
    employment_form: list[hh.EmploymentForm] = [],
    work_format: list[hh.WorkFormat] = [],
    period_days: Annotated[Literal[1, 3, 7, 30] | None, Field(description="Only vacancies published in the last N days")] = None,
    order_by: hh.OrderBy = "relevance",
    page: Annotated[int, Field(ge=0, description="0-based page")] = 0,
    per_page: Literal[20, 50, 100] = 20,
    exclude_applied: Annotated[bool, Field(description="Hide vacancies the user already applied to")] = True,
) -> SearchResult:
    """Search hh.ru vacancies and return structured cards."""
    params = hh.search_params(text, area, salary, only_with_salary, experience, employment_form, work_format,
                              period_days, order_by, page, per_page, search_field)
    state = await client().get_state("/search/vacancy", params)
    return hh.parse_search(state, account.load_applied(), exclude_applied)


@mcp.tool()
async def get_vacancy(vacancy_id: int) -> VacancyDetails:
    """Full vacancy: description as markdown, key skills, conditions, and whether the user applied."""
    return hh.parse_vacancy(await client().get_state(f"/vacancy/{vacancy_id}"), account.load_applied())


@mcp.tool()
async def login(timeout_sec: Annotated[int, Field(ge=30, le=900)] = 300) -> dict:
    """Open a Chrome window for the user to log in to hh.ru (phone, code, captcha), then sync applied vacancies.
    The user must act in the window; tell them before calling."""
    return await account.login(timeout_sec)


@mcp.tool()
async def sync_applied() -> dict:
    """Refresh the list of vacancies the user applied to (needs an earlier login)."""
    return await account.sync_applied()


def main() -> None:
    if sys.argv[1:2] == ["login"]:
        print(json.dumps(asyncio.run(account.login()), ensure_ascii=False))
    else:
        mcp.run()
