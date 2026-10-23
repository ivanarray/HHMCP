# hh-mcp

MCP server that searches vacancies on hh.ru and returns structured cards. Optionally logs in to your account to hide vacancies you already applied to.

- Search and vacancy pages are fetched anonymously with a Chrome TLS/HTTP2 fingerprint (`curl_cffi`), rotating over proxy ports, one request at a time with random pauses. A port that hits a block or captcha rests for 10 minutes.
- The account lives only in a real Chrome profile (`data/browser-profile`, Playwright) that connects directly, without a proxy, like your own browser. Its cookies never reach the search client, and searches always go through the proxies, so they are never made as your account or from your IP. Applied vacancies are filtered locally from `data/applied.json`.

## Setup

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/) and Google Chrome installed in the system.

```sh
cp config.example.yaml config.yaml   # fill in your proxies
uv sync
```

`proxies` is a list, each with its own `type` (`http` by default, or `socks5`), host, ports and optional login/password. `ports` is a range like `10000-10010`, a list or one port, each port being a different exit IP. Ports of all proxies form one pool for search; one port is enough. The account does not use proxies.

Add to your agent, it runs the server over stdio:

```sh
claude mcp add hh -- uv run --directory /path/to/HHMcp hh-mcp   # Claude Code
codex mcp add hh -- uv run --directory /path/to/HHMcp hh-mcp    # Codex CLI
pi mcp add hh -- uv run --directory /path/to/HHMcp hh-mcp       # pi, then `pi mcp list` to check
```

Codex cuts tool calls after 300 seconds, while `login` waits up to 15 minutes for you. To give it time, set the timeout in `~/.codex/config.toml`:

```toml
[mcp_servers.hh]
command = "uv"
args = ["run", "--directory", "/path/to/HHMcp", "hh-mcp"]
tool_timeout_sec = 900
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
