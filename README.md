# hh-mcp

MCP server that searches vacancies on hh.ru and returns structured cards. Optionally logs in to your account to hide vacancies you already applied to.

- Search and vacancy pages are fetched anonymously with a Chrome TLS/HTTP2 fingerprint (`curl_cffi`), rotating over proxy ports, one request at a time with random pauses. A port that hits a block or captcha rests for 10 minutes.
- The account lives only in a real Chrome profile (`data/browser-profile`, Playwright) that always uses the first proxy port. Its cookies never reach the search client, so searches are never made as your account. Applied vacancies are filtered locally from `data/applied.json`.

## Setup

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/) and Google Chrome installed in the system.

```sh
cp .env.example .env   # fill in proxy host, port range, login, password
uv sync
```

`PROXY_PORTS` is a range like `10000-10010`, each port being a different exit IP. The first port is reserved for the account, the rest are used for search.

Add to Claude Code:

```sh
claude mcp add hh -- uv run --directory /path/to/HHMcp hh-mcp
```

## Tools

| Tool | What it does |
|------|--------------|
| `search_vacancies` | Search with text, region, salary, experience, employment form, work format, period, sort, paging. Hides applied vacancies by default. |
| `get_vacancy` | Full vacancy: markdown description, key skills, conditions, applied flag. |
| `login` | Opens a Chrome window, you log in (phone, code, captcha), then applied vacancies are synced. |
| `sync_applied` | Refreshes the applied list using the saved session. |

If your MCP client drops the long `login` call, log in from a terminal instead: `uv run hh-mcp login`.

## Tests

```sh
uv run pytest
```

Parsers are tested on trimmed real pages in `tests/fixtures`. hh.ru changes its page state from time to time; a failing parser test after re-capturing a fixture shows what moved.
