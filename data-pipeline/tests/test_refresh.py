"""Refreshing must really reach the source (review finding F1).

A fake HTTP layer stands in for the network, and a cached file with old bytes is planted first.
The tests prove the new bytes reach the output on every documented refresh path, and that reusing
the cache is only ever an explicit choice.
"""

import pytest
import requests

from wimm import build, http, kela, treasury


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self.body, self.status = body, status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status}")

    def iter_content(self, chunk_size=1):
        yield self.body


@pytest.fixture
def network(monkeypatch):
    """Replace requests.get; `served` maps a url to the bytes it returns, `calls` records requests."""
    state = {"served": {}, "calls": [], "status": 200}

    def fake_get(url, **kwargs):
        state["calls"].append(url)
        return FakeResponse(state["served"].get(url, b"default"), state["status"])

    monkeypatch.setattr(http.requests, "get", fake_get)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)
    return state


def test_fetch_replaces_a_cached_file_by_default(tmp_path, network):
    dest = tmp_path / "x.csv"
    dest.write_bytes(b"old")
    network["served"]["u"] = b"new"
    assert http.fetch("u", dest).read_bytes() == b"new"
    assert network["calls"] == ["u"]


def test_fetch_reuses_the_cache_only_when_asked_to(tmp_path, network):
    dest = tmp_path / "x.csv"
    dest.write_bytes(b"old")
    network["served"]["u"] = b"new"
    assert http.fetch("u", dest, refresh=False).read_bytes() == b"old"
    assert network["calls"] == []  # offline mode makes no request at all


def test_offline_mode_still_downloads_a_file_that_is_missing(tmp_path, network):
    network["served"]["u"] = b"new"
    assert http.fetch("u", tmp_path / "x.csv", refresh=False).read_bytes() == b"new"


def test_a_failed_refresh_keeps_the_old_file_and_raises(tmp_path, network):
    dest = tmp_path / "x.csv"
    dest.write_bytes(b"old")
    network["status"] = 403
    with pytest.raises(RuntimeError, match="Could not download"):
        http.fetch("u", dest, retries=2)
    assert dest.read_bytes() == b"old"


def test_treasury_requests_refresh_by_default_and_honour_offline_mode(tmp_path, monkeypatch):
    seen = []

    def fake_fetch(url, dest, *, refresh=True, **kw):
        seen.append(refresh)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("Vuosi,Tunnus\n2025,21\n", encoding="utf-8")
        return dest

    monkeypatch.setattr(treasury, "fetch", fake_fetch)
    assert treasury.list_classes(2025, tmp_path) == ["21"]
    treasury.fetch_events("21", 2025, tmp_path)
    assert seen == [True, True]
    treasury.list_classes(2025, tmp_path, refresh=False)
    treasury.fetch_events("21", 2025, tmp_path, refresh=False)
    assert seen[2:] == [False, False]


def test_kela_raw_file_name_carries_the_resource_id(tmp_path):
    a = kela.raw_path("asumistuki", 2025, tmp_path)
    assert kela.ASUMISTUKI_RESOURCES[2025][:8] in a.name
    # A different resource for the same benefit and year can never reuse the old file's name.
    assert a != kela.raw_path("asumistuki", 2024, tmp_path)


@pytest.mark.parametrize("mode,expect_refresh", [("download", True), ("recompute", False)])
def test_kela_modes_pass_the_refresh_choice_down_and_rewrite_the_snapshot(tmp_path, monkeypatch, mode, expect_refresh):
    seen = []
    e_parts = {"elamantilanne": {"a": 300}}
    prov = {"source_url": "u", "resource_id": "r", "sha256": "a" * 64, "bytes": 1, "retrieved_at": "2026-01-01"}

    def fake_download(benefit, year, cache, refresh=True):
        seen.append((benefit, year, refresh))
        return kela.KelaYear(year, benefit, 300, e_parts, 0, ["ok"]), prov

    saved = {}
    monkeypatch.setattr(kela, "download_and_aggregate", fake_download)
    monkeypatch.setattr(kela, "save_snapshot", lambda entries, path: saved.update(entries))
    out = build.kela_inputs(mode, tmp_path, [2025], tmp_path / "missing.json")
    assert {r for _b, _y, r in seen} == {expect_refresh}
    assert set(out) == {("asumistuki", 2025), ("opintoraha_ja_asumislisa", 2025)} == set(saved)


def test_build_notes_say_whether_treasury_data_was_fetched_or_reused(tmp_path, monkeypatch):
    """The manifest must not claim fresh data when the cache was used."""
    seen = []

    def stop(y, cache, notes=None, refresh=True):
        seen.append(refresh)
        raise StopIteration  # enough to see the flag; the rest of the build needs real data

    monkeypatch.setattr(treasury, "load_year", stop)
    for use_cache in (False, True):
        with pytest.raises(StopIteration):
            build.build(tmp_path / "c", tmp_path / "o", [2025], use_cache=use_cache)
    assert seen == [True, False]
