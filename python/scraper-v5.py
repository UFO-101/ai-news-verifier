# ailabwatch_full_scraper_v5.py
# --------------------------------
# Requirements:
#   pip install playwright
#   playwright install
#
# Run:
#   python ailabwatch_full_scraper_v5.py
#
# Output:
#   ./ailabwatch_categories_subcategories_scores_weights.json
#
# What it collects:
# - Category weights (from the Categories overview page)
# - For each category (page):
#     * Subcategory weight ("Weighted NN% of category")
#     * Per-company scores in that subcategory
# - For each subcategory (on the xAI "cell" page for that category):
#     * Rubric/description (expands the “Click to show/hide details/rubric” panel)
#
# Notes:
# - No mixed selector engines. We only use CSS/XPath + small DOM scripts.
# - The rubric toggle search uses XPath "contains(., ...)" for both show/hide variants.
# - If a rubric block is missing or fails to open, description fields are None.

import asyncio
import json
import re
import sys
from contextlib import suppress
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from playwright.async_api import Locator, Page, async_playwright
from playwright.async_api import TimeoutError as PWTimeout

BASE = "https://ailabwatch.org/"

CATEGORIES: List[Tuple[str, str]] = [
    ("risk-assessment", "Risk assessment"),
    ("scheming", "Scheming risk prevention"),
    ("safety-research", "Boosting safety research"),
    ("misuse", "Misuse prevention"),
    ("security", "Prep for extreme security"),
    ("information-sharing", "Risk info sharing"),
    ("planning", "Planning"),
]

COMPANIES = ["Anthropic", "DeepMind", "OpenAI", "Meta", "xAI", "Microsoft", "DeepSeek"]


async def get_category_weights(page: Page) -> Dict[str, Optional[int]]:
    """Parse 'NN % weight' for each category on the overview page."""
    await page.goto(urljoin(BASE, "categories"), wait_until="domcontentloaded")
    with suppress(PWTimeout):
        await page.wait_for_selector("h1, h2, a", timeout=8000)

    body_text = await page.locator("body").inner_text()
    weights: Dict[str, Optional[int]] = {}
    for slug, title in CATEGORIES:
        # Find "<title> ... NN % weight" within a window after the title
        m = re.search(
            re.escape(title) + r".{0,300}?(\d+)\s*%\s*weight",
            body_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        weights[title] = int(m.group(1)) if m else None
    return weights


async def parse_category_page(page: Page, slug: str) -> List[Dict]:
    """For a category page, return list of subcats with weight + per-company scores."""
    await page.goto(urljoin(BASE, f"categories/{slug}"), wait_until="domcontentloaded")
    with suppress(PWTimeout):
        await page.wait_for_selector("h2", timeout=8000)

    subcats: List[Dict] = []
    headers: Locator = page.locator("h2")
    count = await headers.count()
    for i in range(count):
        header = headers.nth(i)
        name = (await header.inner_text()).strip()
        if not name:
            continue

        # Subcategory weight nearby
        weight = None
        for j in range(1, 10):
            sib = header.locator(f"xpath=following::*[{j}]")
            with suppress(Exception):
                txt = (await sib.inner_text()).strip()
                mm = re.search(r"Weighted\s+(\d+)%\s+of category", txt)
                if mm:
                    weight = int(mm.group(1))
                    break

        # Gather text between this h2 and next h2, parse "Image: Company\nNN%"
        span = header.locator("xpath=following-sibling::*")
        span_count = await span.count()
        collected = []
        for k in range(span_count):
            tag = await span.nth(k).evaluate("n => n.tagName")
            if tag == "H2":
                break
            with suppress(Exception):
                collected.append((await span.nth(k).inner_text()).strip())
        joined = "\n".join(collected)

        scores: Dict[str, Optional[int]] = {}
        for comp in COMPANIES:
            mm = re.search(rf"Image:\s*{re.escape(comp)}\s*\n(\d+)%", joined)
            if mm:
                scores[comp] = int(mm.group(1))
        subcats.append({"name": name, "weight": weight, "scores": scores})

    return subcats


async def click_near_toggle(header: Locator) -> None:
    """Click the nearest rubric toggle after the given header (h2/h3),
    matching both 'show' and 'hide' variants, using XPath text contains."""
    # Search first 12 following elements for a button/div/span that contains the toggle text
    toggle = header.locator(
        "xpath=following::*[self::button or self::div or self::span]"
        "[contains(., 'Click to show details/rubric') or contains(., 'Click to hide details/rubric')][1]"
    )
    # Try to click if exists
    try:
        if await toggle.count():
            await toggle.first.click(timeout=3000)
    except Exception:
        # It may already be expanded, or non-clickable. Ignore.
        pass


async def scrape_subcategory_rubrics(
    page: Page, slug: str, subcats: List[Dict]
) -> Dict[str, Dict[str, Optional[str]]]:
    """Open a representative company 'cell' page and extract rubric for each subcat."""
    await page.goto(urljoin(BASE, f"cell/xai/{slug}"), wait_until="domcontentloaded")
    with suppress(PWTimeout):
        await page.wait_for_selector("h3, h2", timeout=8000)

    rubrics: Dict[str, Dict[str, Optional[str]]] = {}
    for sc in subcats:
        title = sc["name"]

        # Find the subcategory header (try h3 then h2, fallback to prefix before colon)
        header = page.locator("h3", has_text=title)
        if await header.count() == 0:
            header = page.locator("h2", has_text=title)
        if await header.count() == 0:
            prefix = title.split(":")[0].strip()
            header = page.locator("h3", has_text=prefix)
        if await header.count() == 0:
            rubrics[title] = {"description": None, "description_html": None}
            continue

        h = header.first
        with suppress(Exception):
            await h.scroll_into_view_if_needed()

        await click_near_toggle(h)

        # The rubric content lives in a `.text-sm.links` block near the header
        rubric_div = h.locator(
            "xpath=following::*[contains(@class, 'text-sm') and contains(@class, 'links')][1]"
        )
        try:
            await rubric_div.wait_for(state="visible", timeout=5000)
            html = await rubric_div.inner_html()
            text = await rubric_div.inner_text()
            rubrics[title] = {"description": text, "description_html": html}
        except PWTimeout:
            # Last-ditch global fallback
            global_div = page.locator("css=div.text-sm.links").first
            if await global_div.count():
                html = await global_div.inner_html()
                text = await global_div.inner_text()
                rubrics[title] = {"description": text, "description_html": html}
            else:
                rubrics[title] = {"description": None, "description_html": None}

    return rubrics


async def build_dataset() -> List[Dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # 1) Category weights (single page)
        cat_page = await context.new_page()
        cat_weights = await get_category_weights(cat_page)
        await cat_page.close()

        out: List[Dict] = []

        # 2) For each category, parse subs + scores + rubrics
        for slug, title in CATEGORIES:
            print(f"Scraping {title}…", file=sys.stderr)
            cat_parse_page = await context.new_page()
            subcats = await parse_category_page(cat_parse_page, slug)
            await cat_parse_page.close()

            rubric_page = await context.new_page()
            rubrics = await scrape_subcategory_rubrics(rubric_page, slug, subcats)
            await rubric_page.close()

            out.append(
                {
                    "category": title,
                    "weight": cat_weights.get(title),
                    "subcategories": [
                        {
                            "name": sc["name"],
                            "weight": sc["weight"],
                            "description": rubrics.get(sc["name"], {}).get(
                                "description"
                            ),
                            "description_html": rubrics.get(sc["name"], {}).get(
                                "description_html"
                            ),
                            "scores": sc["scores"],
                        }
                        for sc in subcats
                    ],
                }
            )

        await context.close()
        await browser.close()
        return out


def main():
    data = asyncio.run(build_dataset())
    out_path = Path("ailabwatch_categories_subcategories_scores_weights.json")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(str(out_path.resolve()))


if __name__ == "__main__":
    main()
