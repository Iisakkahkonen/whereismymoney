"""Download helper with an on-disk cache.

Downloads are written atomically. By default every call fetches from the source.
Reusing files already on disk is an explicit, cache-only choice (refresh=False): it never
touches the network and fails if a file is missing. It is used for offline work and for
re-aggregating the 100 to 300 MB Kela files without downloading them again.
"""

import time
from pathlib import Path

import requests

USER_AGENT = "whereismymoney-pipeline (open source; https://github.com/Iisakkahkonen/whereismymoney)"


class CacheMiss(FileNotFoundError):
    """Offline mode was asked for a file that is not on disk. No request was made."""


def fetch(url: str, dest: Path, *, refresh: bool = True, retries: int = 4, timeout: tuple[int, int] = (30, 90)) -> Path:
    """Download url to dest and return dest.

    refresh=True (the default) always asks the source, so a new run can never silently reuse old
    bytes. A failed refresh leaves the old file untouched.

    refresh=False is the offline, cache-only mode: an existing non-empty file is returned as is, with
    no check that it is current, and a missing or empty file raises CacheMiss. It never makes a
    request, so "offline" is true by construction."""
    if not refresh:
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        raise CacheMiss(f"offline mode needs {dest} (for {url}) but it is missing or empty; run once without the offline flag to fetch it")
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
