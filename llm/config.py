import tomllib
from pathlib import Path


def load_config(path: str = "config.toml") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{path} missing — copy config.example.toml to config.toml")
    with p.open("rb") as f:
        return tomllib.load(f)
