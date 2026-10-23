from pathlib import Path
from typing import Literal
from urllib.parse import quote

import yaml
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CONFIG = ROOT / "config.yaml"


class Proxy(BaseModel):
    model_config = ConfigDict(coerce_numbers_to_str=True)  # YAML reads `ports: 8080` or `password: 1234` as numbers

    type: Literal["http", "socks5"] = "http"
    host: str
    ports: str  # "10000-10010", "10000, 10002" or one port
    login: str = ""
    password: str = ""


class Config(BaseModel):
    proxies: list[Proxy]
    request_delay: tuple[float, float] = (2, 5)  # random pause between search requests, seconds


def load_config(path: Path = CONFIG) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))


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


def proxies(cfg: Config | None = None) -> list[str]:
    """Search proxy URLs, one per port of every proxy."""
    urls = []
    for p in (cfg or load_config()).proxies:
        auth = f"{quote(p.login, safe='')}:{quote(p.password, safe='')}@" if p.login else ""
        scheme = "socks5h" if p.type == "socks5" else "http"  # socks5h: curl resolves DNS through the proxy too
        urls += [f"{scheme}://{auth}{p.host}:{port}" for port in parse_ports(p.ports)]
    if not urls:
        raise ValueError("config.yaml needs at least one proxy port")
    return urls
