import asyncio
import html
import json
import logging
import random
import re
import time

from curl_cffi.requests import AsyncSession
from mcp.server.mcpserver.exceptions import ToolError

from hh_mcp.config import load_env, proxies

log = logging.getLogger(__name__)

BASE = "https://hh.ru"
STATE_RE = re.compile(r'<template[^>]*id="HH-Lux-InitialState"[^>]*>(.*?)</template>', re.S)
COOLDOWN_SEC = 600
ATTEMPTS = 3


class Blocked(ToolError):  # ToolError: the agent sees the message, not a bare "Error executing tool"
    pass


class NotFound(ToolError):
    pass


def extract_state(page: str) -> dict:
    m = STATE_RE.search(page)
    if not m:
        raise Blocked("no HH-Lux-InitialState on page (captcha or layout change)")
    return json.loads(html.unescape(m.group(1)))


class SearchClient:
    """Anonymous hh.ru client: one curl_cffi session (own cookie jar) per search proxy, one request at a time."""

    def __init__(self, search_proxies: list[str] | None = None):
        env = load_env()
        self.delay = (float(env.get("REQUEST_DELAY_MIN", 2)), float(env.get("REQUEST_DELAY_MAX", 5)))
        self.proxies = search_proxies if search_proxies is not None else proxies(env)[1]
        self.sessions: dict[str, AsyncSession] = {}
        self.cooldown: dict[str, float] = {}
        self.next = 0
        self.lock = asyncio.Lock()
        self.last = 0.0

    def _pick(self) -> str:
        now = time.monotonic()
        for _ in self.proxies:
            proxy = self.proxies[self.next % len(self.proxies)]
            self.next += 1
            if self.cooldown.get(proxy, 0) <= now:
                return proxy
        raise Blocked("all search proxies are cooling down after blocks, try again later")

    async def _session(self, proxy: str) -> AsyncSession:
        if proxy not in self.sessions:
            # stored before the warm-up, so a failed warm-up is closed by get_state's error path
            s = self.sessions[proxy] = AsyncSession(
                proxy=proxy, impersonate="chrome", timeout=30,
                headers={"Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"},
            )
            await s.get(BASE + "/")  # warm-up: pick up anonymous cookies like a first visit
        return self.sessions[proxy]

    async def get_state(self, path: str, params: dict | None = None) -> dict:
        async with self.lock:
            for attempt in range(ATTEMPTS):
                await asyncio.sleep(max(0.0, self.last + random.uniform(*self.delay) - time.monotonic()))
                proxy = self._pick()
                try:
                    s = await self._session(proxy)
                    r = await s.get(BASE + path, params=params, headers={"Referer": BASE + "/"})
                    if r.status_code in (403, 429) or "captcha" in r.url:
                        raise Blocked(f"HTTP {r.status_code} {r.url}")
                    if r.status_code == 404:
                        raise NotFound(f"not found on hh.ru: {path}")
                    if r.status_code >= 500:
                        continue  # hh.ru itself failed, not this IP: retry without the cooldown
                    return extract_state(r.text)
                except NotFound:
                    raise
                except Exception as e:  # blocks, proxy and network errors: rest this IP, retry on the next one
                    log.warning("proxy port %s failed (attempt %d): %s", proxy.rsplit(":", 1)[-1], attempt + 1, e)
                    self.cooldown[proxy] = time.monotonic() + COOLDOWN_SEC
                    if s := self.sessions.pop(proxy, None):
                        await s.close()
                finally:
                    self.last = time.monotonic()
            raise Blocked(f"hh.ru blocked {ATTEMPTS} proxies in a row, try again later")
