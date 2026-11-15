"""Headless browser tests against the built site (web/dist).

Run after `npm run build` in web/. They gate every deploy (CLAUDE.md).
    pip install pytest playwright pyarrow && playwright install chromium
    pytest e2e
"""

import functools
import http.server
import json
import threading
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from playwright.sync_api import Page, expect, sync_playwright

DIST = Path(__file__).parent.parent / "web" / "dist"
DATA = DIST / "data"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep test output readable
        pass


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(Quiet, directory=str(DIST))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/"
    server.shutdown()


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser, base_url):
    ctx = browser.new_context(viewport={"width": 1100, "height": 900}, locale="en-GB")
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.goto(base_url)
    pg.wait_for_selector("body[data-ready='overview']", timeout=60_000)
    yield pg
    ctx.close()


@pytest.fixture(scope="session")
def manifest():
    return json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))


def spending_total(year: int) -> float:
    rows = pq.read_table(DATA / "budget_items.parquet").to_pylist()
    return sum(r["actual_eur"] for r in rows if r["year"] == year and r["side"] == "expenditure" and r["actual_eur"] > 0)


def test_overview_loads_without_errors(page):
    expect(page.locator("h1, .brand").first).to_contain_text("Where is my money?")
    expect(page.locator("#treemap canvas")).to_be_visible()
    expect(page.locator("#compare canvas")).to_be_visible()
    assert page.errors == []


def test_headline_total_matches_the_parquet_data(page, manifest):
    """The number on the page is the same as an independent sum of the built data."""
    year = manifest["years"][-1]
    shown = page.locator("#total-spent").inner_text()  # for example "86.76 bn€"
    expected = spending_total(year) / 1e9
    assert shown.endswith("bn€")
    assert float(shown.replace("bn€", "").strip().replace(",", ".")) == pytest.approx(expected, abs=0.006)


def test_traced_items_are_listed_with_their_share(page):
    items = page.locator("#traced-items li")
    expect(items).to_have_count(2)
    expect(page.locator("#traced-items")).to_contain_text("Asumistuki")


def test_search_suggests_in_english_and_finnish(page):
    box = page.locator("#search")
    for query in ("housing allowance", "asumistuki"):
        box.fill("")
        box.type(query)
        option = page.locator("#suggestions [role=option]").first
        expect(option).to_be_visible()
        expect(page.locator("#suggestions")).to_contain_text("housing allowance", ignore_case=True)


def test_search_result_opens_item_with_coverage_and_sources(page):
    page.locator("#search").type("housing allowance")
    page.locator("#suggestions [role=option]").first.click()
    page.wait_for_selector("body[data-ready='item']")
    expect(page.locator("#item-title")).to_have_text("General housing allowance")
    expect(page.locator(".meter")).to_have_attribute("aria-label", __import__("re").compile(r"traced \d"))
    expect(page.locator("#coverage-note")).to_contain_text("Kela reports")
    hrefs = page.locator("main a[target=_blank]").evaluate_all("els => els.map(e => e.href)")
    assert any("momentti=331054" in h and "tutkihallintoa.fi" in h for h in hrefs)
    assert any("avoindata.suomi.fi" in h for h in hrefs)
    assert page.locator("main canvas").count() >= 2  # trend and breakdown
    assert page.errors == []


def test_item_without_a_source_says_it_is_not_traced(page):
    page.goto(page.url.split("#")[0] + "#/item/110101")  # a revenue item: income and capital taxes
    page.wait_for_selector("body[data-ready='item']")
    expect(page.locator("#coverage-note")).to_contain_text("All of it is shown as not traced")


def test_unknown_item_is_handled(page):
    page.goto(page.url.split("#")[0] + "#/item/999999")
    page.wait_for_selector("body[data-ready='item']")
    expect(page.locator("main")).to_contain_text("Nothing found")


def test_year_selector_changes_the_headline(page, manifest):
    years = manifest["years"]
    if len(years) < 2:
        pytest.skip("needs at least two years of data")
    before = page.locator("#total-spent").inner_text()
    page.select_option("#year", str(years[0]))
    page.wait_for_function("document.querySelector('.hero h2').textContent.includes('%d')" % years[0])
    assert page.locator("#total-spent").inner_text() != before
    expect(page.locator("#year")).to_have_value(str(years[0]))


def test_language_switch_gives_finnish(page):
    page.get_by_role("button", name="FI").click()
    expect(page.locator(".brand")).to_have_text("Mihin rahani menevät?")
    assert page.evaluate("document.documentElement.lang") == "fi"
    expect(page.locator(".hero h2")).to_contain_text("Valtion budjetin menot")


def test_sources_page_credits_kela(page):
    page.get_by_role("link", name="Sources and method").click()
    page.wait_for_selector("body[data-ready='sources']")
    expect(page.locator("main")).to_contain_text("Source: Kela (Kelasto), licensed CC BY 4.0.")
    expect(page.locator("main")).to_contain_text("What is not covered")


def test_no_horizontal_scroll_on_a_phone(browser, base_url):
    ctx = browser.new_context(viewport={"width": 375, "height": 800}, is_mobile=True)
    pg = ctx.new_page()
    pg.goto(base_url)
    pg.wait_for_selector("body[data-ready='overview']", timeout=60_000)
    assert pg.evaluate("document.documentElement.scrollWidth") <= 375
    ctx.close()
