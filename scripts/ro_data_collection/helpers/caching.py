import hashlib
import json
import re

from pathlib import Path

def _cache_key(query: str) -> str:
    """Deterministic key for a query string"""
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:80]
    short_hash = hashlib.sha256(query.encode()).hexdigest()[:10]
    return f"{slug}_{short_hash}"

def _meta_path(cache_dir: Path, key: str) -> Path:
    """Meta-data path"""
    return cache_dir / key / "meta.json"

def load_meta(cache_dir: Path, key: str) -> dict | None:
    p = _meta_path(cache_dir, key)
    if p.exists():
        return json.loads(p.read_text())
    return None

def save_meta(cache_dir: Path, key: str, meta: dict) -> None:
    d = cache_dir / key
    d.mkdir(parents=True, exist_ok=True)
    _meta_path(cache_dir, key).write_text(json.dumps(meta, indent=2))

def save_page(cache_dir: Path, key: str, page: int, data: dict) -> None:
    d = cache_dir / key
    d.mkdir(parents=True, exist_ok=True)
    (d / f"page_{page}.json").write_text(json.dumps(data, indent=2))

def load_page(cache_dir: Path, key: str, page: int) -> dict | None:
    p = cache_dir / key / f"page_{page}.json"
    if p.exists():
        return json.loads(p.read_text())
    return None
