"""Download helper with an on-disk cache.

The Kela files are 100 to 300 MB each, so downloads are cached by file name
and written atomically. CI keeps the cache directory between runs.
"""

import time
from pathlib import Path

import requests

USER_AGENT = "whereismymoney-pipeline (open source; https://github.com/Iisakkahkonen/whereismymoney)"


def fetch(url: str, dest: Path, *, retries: int = 4, timeout: tuple[int, int] = (30, 90)) -> Path:
    """Download url to dest unless it is already cached. Returns dest."""
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": USER_AGENT}) as r:
                r.raise_for_status()
                with open(part, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
            part.replace(dest)
            return dest
        except requests.RequestException as e:  # network or HTTP error: retry, then fail loudly
            last = e
            time.sleep(2 * attempt)
    raise RuntimeError(f"Could not download {url} after {retries} attempts: {last}")
