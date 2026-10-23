import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit

from playwright.async_api import BrowserContext, async_playwright

from hh_mcp.client import BASE, extract_state
from hh_mcp.config import DATA_DIR, proxies

log = logging.getLogger(__name__)

PROFILE = DATA_DIR / "browser-profile"
APPLIED = DATA_DIR / "applied.json"
NEGOTIATIONS = BASE + "/applicant/negotiations"
_lock = asyncio.Lock()  # one Chrome per profile at a time


def load_applied() -> set[int] | None:
    if not APPLIED.exists():
        return None
    return set(json.loads(APPLIED.read_text())["ids"])


async def _browser(p, headless: bool) -> BrowserContext:
    """Real Chrome with the persistent account profile, always via the login proxy (first port)."""
    u = urlsplit(proxies()[0])
    PROFILE.mkdir(parents=True, exist_ok=True)
    return await p.chromium.launch_persistent_context(
        PROFILE, channel="chrome", headless=headless, locale="ru-RU", timezone_id="Europe/Moscow",
        proxy={"server": f"http://{u.hostname}:{u.port}", "username": unquote(u.username or ""),
               "password": unquote(u.password or "")},
    )


async def login(timeout_sec: int = 300) -> dict:
    """Open a visible Chrome on the hh.ru login page and wait until the user is in the applicant area."""
    async with _lock, async_playwright() as p:
        ctx = await _browser(p, headless=False)
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.goto(f"{BASE}/account/login?backurl=/applicant/negotiations")
            await page.wait_for_url(re.compile(r"hh\.ru/applicant/"), timeout=timeout_sec * 1000)
        finally:
            await ctx.close()
    return await sync_applied()


def parse_negotiations(state: dict) -> tuple[list[int], bool]:
    """Vacancy ids on one page of /applicant/negotiations and whether a next page exists."""
    # shortcut: reads the default "active" tab only (hh ignores filter params); archived responses would be missed
    n = state["applicantNegotiations"]
    ids = [t["vacancyId"] for t in n["topicList"] if t.get("vacancyId")]
    return ids, not n["paging"]["next"]["disabled"]


async def sync_applied() -> dict:
    """Collect ids of every vacancy the account applied to and store them in data/applied.json."""
    ids: set[int] = set()
    async with _lock, async_playwright() as p:
        ctx = await _browser(p, headless=True)
        try:
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            for n in range(1000):
                await page.goto(f"{NEGOTIATIONS}?page={n}")
                if "/account/login" in page.url:
                    return {"logged_in": False, "hint": "session expired, call login"}
                page_ids, has_next = parse_negotiations(extract_state(await page.content()))
                ids.update(page_ids)
                if not has_next:
                    break
                await asyncio.sleep(2)
        finally:
            await ctx.close()
    synced_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    DATA_DIR.mkdir(exist_ok=True)
    tmp = APPLIED.with_suffix(".tmp")
    tmp.write_text(json.dumps({"ids": sorted(ids), "synced_at": synced_at}))
    tmp.replace(APPLIED)
    return {"logged_in": True, "applied_count": len(ids), "synced_at": synced_at}
