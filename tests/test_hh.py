import asyncio
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote, urlsplit

import pytest

from hh_mcp import hh
from hh_mcp.account import parse_negotiations
from hh_mcp.client import Blocked, NotFound, SearchClient, extract_state
from hh_mcp.config import Config, Proxy, load_config, parse_ports, proxies

FIX = Path(__file__).parent / "fixtures"


def state(name: str) -> dict:
    return extract_state((FIX / name).read_text())


def test_parse_search():
    r = hh.parse_search(state("search.html"), applied=None, exclude_applied=True)
    assert (r.total, r.page, r.pages, len(r.items)) == (39, 0, 2, 3)
    assert r.applied_filter == "unavailable: run login"
    c = r.items[0]
    assert c.id == 138790793 and c.url == "https://hh.ru/vacancy/138790793"
    assert (c.salary_from, c.salary_to, c.currency, c.salary_gross) == (230000, 270000, "RUR", True)
    assert c.work_formats == ["REMOTE"] and c.schedule == ["FIVE_ON_TWO_OFF"]
    assert c.company and c.company_rating == 1.2 and c.has_test


def test_parse_search_hides_applied():
    first = hh.parse_search(state("search.html"), None, True).items[0].id
    r = hh.parse_search(state("search.html"), applied={first}, exclude_applied=True)
    assert r.applied_filtered == 1 and first not in [c.id for c in r.items]
    assert len(hh.parse_search(state("search.html"), {first}, exclude_applied=False).items) == 3


def test_parse_vacancy():
    v = hh.parse_vacancy(state("vacancy.html"), applied={138790793})
    assert v.title == "Сетевой инженер" and v.applied is True
    assert "**Обязанности:**" in v.description and "Python" in v.key_skills
    assert v.work_formats == ["REMOTE"] and v.salary_from == 230000


def test_search_params_repeat_multi_select():
    p = hh.search_params("python", 1, 200000, True, ["between1And3", "between3And6"], [], ["REMOTE"], 7,
                         "publication_time", 0, 20)
    assert ("experience", "between1And3") in p and ("experience", "between3And6") in p
    assert ("only_with_salary", "true") in p and ("search_period", 7) in p
    p = hh.search_params("go", 1, None, False, [], [], [], None, "relevance", 0, 20, ["name"])
    assert ("search_field", "name") in p


def test_flat_handles_empty_nested_lists():
    assert hh._flat([{}]) == [] and hh._flat([{"x": ["A", "B"]}]) == ["A", "B"] and hh._flat(["A"]) == ["A"]


def test_page_without_state_is_blocked():
    with pytest.raises(Blocked):
        extract_state("<html>captcha</html>")


def test_proxies_from_yaml(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "proxies:\n"
        "  - {host: p.example, ports: 10000-10001, login: u, password: 'p@ss#1/:'}\n"
        "  - {type: socks5, host: q.example, ports: 8080}\n"
        "request_delay: [0, 1]\n"
    )
    cfg = load_config(tmp_path / "config.yaml")
    urls = proxies(cfg)
    assert urls == ["http://u:p%40ss%231%2F%3A@p.example:10000", "http://u:p%40ss%231%2F%3A@p.example:10001",
                    "socks5h://q.example:8080"]
    assert unquote(urlsplit(urls[0]).password or "") == "p@ss#1/:"
    assert cfg.request_delay == (0, 1) and parse_ports("1, 3-4") == [1, 3, 4]
    assert proxies(Config(proxies=[Proxy(host="p.example", ports="10000")])) == ["http://p.example:10000"]
    with pytest.raises(ValueError):
        proxies(Config(proxies=[]))


def fake_client(*responses: tuple[int, str]) -> SearchClient:
    """SearchClient over two fake proxies whose sessions answer with (status, body) in order."""
    queue = [SimpleNamespace(status_code=code, url="https://hh.ru/x", text=body) for code, body in responses]

    async def get(*args, **kwargs):
        return queue.pop(0)

    async def session(proxy):
        return SimpleNamespace(get=get)

    c = SearchClient(Config(proxies=[Proxy(host="p", ports="1-3")], request_delay=(0, 0)))
    c._session = session
    return c


def test_get_state_rests_only_blocked_proxies():
    page = (FIX / "search.html").read_text()
    c = fake_client((403, ""), (200, page))
    assert "vacancySearchResult" in asyncio.run(c.get_state("/x")) and list(c.cooldown) == ["http://p:1"]
    c = fake_client((502, ""), (200, page))
    asyncio.run(c.get_state("/x"))
    assert c.cooldown == {}
    c = fake_client((404, ""))
    with pytest.raises(NotFound):
        asyncio.run(c.get_state("/x"))
    assert c.cooldown == {}


def test_parse_negotiations():
    page = {"applicantNegotiations": {
        "topicList": [{"id": 1, "vacancyId": 111}, {"id": 2, "vacancyId": 222}, {"id": 3, "vacancyId": None}],
        "paging": {"next": {"page": 1, "disabled": False}},
    }}
    assert parse_negotiations(page) == ([111, 222], True)
    page["applicantNegotiations"]["paging"]["next"]["disabled"] = True
    assert parse_negotiations(page)[1] is False
