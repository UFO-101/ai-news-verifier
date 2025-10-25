# ailabwatch_scraper_robust.py
# Scrapes AI Lab Watch category pages, expands each subcategory's rubric, and exports:
#   {
#     "<Category>": {
#       "<Subcategory>": {
#         "description_html": "...",
#         "description": "...",
#         "weight": <int>,
#         "official_scores": {"Anthropic": ..., ...}
#       }, ...
#     }, ...
#   }
#
# Requirements:
#   pip install playwright
#   playwright install
#
# Run:
#   python ailabwatch_scraper_robust.py

import asyncio
import json
import re
import sys
from contextlib import suppress
from pathlib import Path
from typing import Dict
from urllib.parse import urljoin

from playwright.async_api import TimeoutError as PWTimeout
from playwright.async_api import async_playwright

BASE = "https://ailabwatch.org/"

CATEGORIES = [
    ("risk-assessment", "Risk assessment"),
    ("scheming", "Scheming risk prevention"),
    ("safety-research", "Boosting safety research"),
    ("misuse", "Misuse prevention"),
    ("security", "Prep for extreme security"),
    ("information-sharing", "Risk info sharing"),
    ("planning", "Planning"),
]

COMPANIES = ["Anthropic", "DeepMind", "OpenAI", "Meta", "xAI", "Microsoft", "DeepSeek"]

WEIGHT_RE = re.compile(r"Weighted\s+(\d+)%\s+of category", re.I)


def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


async def _extract_subcategories(page) -> list[dict]:
    """On a /categories/<slug> page, collect subcategory name, weight, and per-company scores."""
    subcats = []
    nodes = page.locator("h2")
    count = await nodes.count()
    for i in range(count):
        name = _norm_space(await nodes.nth(i).inner_text())
        if not name:
            continue

        # Weight near the header
        weight = None
        for j in range(1, 12):
            sib = nodes.nth(i).locator(f"xpath=following::*[{j}]")
            with suppress(Exception):
                txt = _norm_space(await sib.inner_text())
                m = WEIGHT_RE.search(txt)
                if m:
                    weight = int(m.group(1))
                    break

        # Collect block text until next h2; parse "Image: Company" followed by NN%
        span = nodes.nth(i).locator("xpath=following-sibling::*")
        span_count = await span.count()
        collected = []
        for k in range(span_count):
            tag = await span.nth(k).evaluate("n => n.tagName")
            if tag == "H2":
                break
            with suppress(Exception):
                collected.append(await span.nth(k).inner_text())
        joined = "\n".join(collected)

        scores = {}
        for comp in COMPANIES:
            m = re.search(rf"Image:\s*{re.escape(comp)}\s*\n(\d+)%", joined)
            if m:
                scores[comp] = int(m.group(1))

        subcats.append({"name": name, "weight": weight, "official_scores": scores})
    return subcats


async def _extract_rubrics(context, slug: str, subcats: list[dict]) -> Dict[str, dict]:
    """Open a representative company cell page (/cell/xai/<slug>), expand each rubric, read HTML/text."""
    page = await context.new_page()
    url = urljoin(BASE, f"cell/xai/{slug}")
    await page.goto(url, wait_until="domcontentloaded")

    with suppress(PWTimeout):
        await page.wait_for_selector("h3, h2", timeout=8000)

    rubrics: Dict[str, dict] = {}

    for sc in subcats:
        title = sc["name"]

        # Find the subcategory header (h3 preferred, h2 fallback; then prefix before colon)
        header = page.locator("h3", has_text=title)
        if await header.count() == 0:
            header = page.locator("h2", has_text=title)
        if await header.count() == 0:
            prefix = title.split(":")[0].strip()
            if prefix:
                header = page.locator("h3", has_text=prefix)
        if await header.count() == 0:
            continue

        h = header.first
        with suppress(Exception):
            await h.scroll_into_view_if_needed()

        # Click the nearest toggle with show/hide rubric wording (robust selectors, no mixed engines)
        toggle = h.locator(
            "xpath=following::*[self::button or self::div or self::span]"
            "[contains(., 'Click to show details/rubric') or contains(., 'Click to hide details/rubric')][1]"
        )
        if await toggle.count() == 0:
            near = h.locator("xpath=following::*[position()<=14]")
            btn = near.get_by_role(
                "button",
                name=re.compile(r"(Click to )?(show|hide) details/?rubric", re.I),
            )
            if await btn.count():
                toggle = btn.first

        with suppress(Exception):
            await toggle.click(timeout=3000)
            await page.wait_for_timeout(150)  # settle small animations

        # Read the rubric content right after the header
        rubric_div = h.locator(
            "xpath=following::*[contains(@class,'text-sm') and contains(@class,'links')][1]"
        )
        try:
            await rubric_div.wait_for(state="visible", timeout=5000)
            html = await rubric_div.inner_html()
            text = await rubric_div.inner_text()
            rubrics[title] = {"html": html, "text": _norm_space(text)}
        except PWTimeout:
            # Global fallback if DOM varies
            global_div = page.locator("css=div.text-sm.links").first
            if await global_div.count():
                html = await global_div.inner_html()
                text = await global_div.inner_text()
                rubrics[title] = {"html": html, "text": _norm_space(text)}

    await page.close()
    return rubrics


async def extract_category(context, slug: str) -> Dict[str, dict]:
    page = await context.new_page()
    url = urljoin(BASE, f"categories/{slug}")
    await page.goto(url, wait_until="domcontentloaded")
    with suppress(PWTimeout):
        await page.wait_for_selector("h1", timeout=6000)
    with suppress(PWTimeout):
        await page.wait_for_selector("h2", timeout=6000)

    subcats = await _extract_subcategories(page)
    await page.close()

    rubrics = await _extract_rubrics(context, slug, subcats)

    out = {}
    for sc in subcats:
        name = sc["name"]
        r = rubrics.get(name, {})
        out[name] = {
            "description_html": r.get("html"),
            "description": r.get("text"),
            "weight": sc.get("weight"),
            "official_scores": sc.get("official_scores", {}),
        }
    return out


async def main():
    out: Dict[str, Dict] = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        for slug, cat_name in CATEGORIES:
            print(f"Scraping {cat_name}…", file=sys.stderr)
            try:
                out[cat_name] = await extract_category(context, slug)
            except Exception as e:
                print(f"[WARN] {cat_name} failed: {e}", file=sys.stderr)
                out[cat_name] = {}
        await context.close()
        await browser.close()

    path = Path("ailabwatch_subcategory_rubrics.json")
    with path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(path.resolve())


if __name__ == "__main__":
    asyncio.run(main())
