import os
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    """Read KEY=VALUE lines from .env; real environment variables win."""
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.lstrip().startswith("#"):
                env[key.strip()] = value.strip().strip("\"'")
    return env | dict(os.environ)


def parse_ports(spec: str) -> list[int]:
    """'10000-10003' or '10000,10001' -> [10000, ...]."""
    ports = []
    for part in spec.replace(" ", ",").split(","):
        if "-" in part:
            lo, hi = map(int, part.split("-"))
            ports.extend(range(lo, hi + 1))
        elif part:
            ports.append(int(part))
    return ports


def proxies(env: dict[str, str] | None = None) -> tuple[str, list[str]]:
    """Return (login_proxy, search_proxies). The first port is reserved for the account."""
    env = env or load_env()
    ports = parse_ports(env["PROXY_PORTS"])
    if len(ports) < 2:
        raise ValueError("PROXY_PORTS needs at least 2 ports: one for login, the rest for search")
    auth = f"{quote(env['PROXY_LOGIN'], safe='')}:{quote(env['PROXY_PASSWORD'], safe='')}@" if env.get("PROXY_LOGIN") else ""
    urls = [f"http://{auth}{env['PROXY_HOST']}:{p}" for p in ports]
    return urls[0], urls[1:]
