# ailabwatch_full_scraper.py
# Requirements:
#   pip install playwright
#   playwright install
#
# Run:
#   python ailabwatch_full_scraper.py
#
# Output:
#   ./ailabwatch_categories_subcategories_scores_weights.json

import asyncio
import json
import re
import sys
from contextlib import suppress
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from playwright.async_api import TimeoutError as PWTimeout
from playwright.async_api import async_playwright

BASE = "https://ailabwatch.org/"

# Canonical category slugs and human-readable names (stable as of site structure).
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


async def get_category_weights(context) -> Dict[str, Optional[int]]:
    """
    Visit the Categories overview page and try to parse the per-category weights like "27 % weight".
    Returns dict: {Readable Category Name -> weight or None}.
    """
    page = await context.new_page()
    url = urljoin(BASE, "categories")
    await page.goto(url, wait_until="domcontentloaded")

    # Give the page a moment to render dynamic content
    with suppress(PWTimeout):
        await page.wait_for_selector("h1, h2, a", timeout=8000)

    # Extract full visible text and try robust regex around each category's title
    body_text = await page.locator("body").inner_text()
    weights: Dict[str, Optional[int]] = {}

    for slug, title in CATEGORIES:
        # Search for "<title> ... <NN> % weight" within a limited window after the title to avoid collisions
        # Use a DOTALL limited window: up to ~300 chars after the title
        pattern = re.compile(
            re.escape(title) + r".{0,300}?(\d+)\s*%\s*weight",
            flags=re.IGNORECASE | re.DOTALL,
        )
        m = pattern.search(body_text)
        weights[title] = int(m.group(1)) if m else None

    await page.close()
    return weights


async def parse_category_page(context, slug: str) -> List[Dict]:
    """
    Scrape a single category page:
      - For each subcategory (h2):
          * subcategory weight ("Weighted NN% of category")
          * per-company scores (Image: Company ... NN%)
    Returns a list of dicts: [{"name": str, "weight": int|None, "scores": {...}}]
    """
    page = await context.new_page()
    url = urljoin(BASE, f"categories/{slug}")
    await page.goto(url, wait_until="domcontentloaded")
    with suppress(PWTimeout):
        await page.wait_for_selector("h2", timeout=8000)

    subcats = []
    headers = page.locator("h2")
    count = await headers.count()
    for i in range(count):
        header = headers.nth(i)
        name = (await header.inner_text()).strip()
        if not name:
            continue

        # Subcategory weight: search a few following siblings for "Weighted NN% of category"
        weight = None
        for j in range(1, 10):
            sib = header.locator(f"xpath=following::*[{j}]")
            with suppress(Exception):
                txt = (await sib.inner_text()).strip()
                m = re.search(r"Weighted\s+(\d+)%\s+of category", txt)
                if m:
                    weight = int(m.group(1))
                    break

        # Extract the text between this h2 and the next h2 to parse company scores
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

        scores = {}
        for comp in COMPANIES:
            m = re.search(rf"Image:\s*{re.escape(comp)}\s*\n(\d+)%", joined)
            if m:
                scores[comp] = int(m.group(1))

        subcats.append({"name": name, "weight": weight, "scores": scores})

    await page.close()
    return subcats


async def scrape_subcategory_rubrics(
    context, slug: str, subcats: List[Dict]
) -> Dict[str, Dict[str, Optional[str]]]:
    """
    For rubric text per subcategory, open a representative "cell" page (xAI works well)
    and expand the 'Click to show details/rubric' toggle under each subcategory title.
    Returns dict: { subcategory name -> { "description": text, "description_html": html } }
    """
    page = await context.new_page()
    url = urljoin(BASE, f"cell/xai/{slug}")
    await page.goto(url, wait_until="domcontentloaded")

    with suppress(PWTimeout):
        await page.wait_for_selector("h3, h2", timeout=8000)

    rubrics: Dict[str, Dict[str, Optional[str]]] = {}

    for sc in subcats:
        title = sc["name"]
        # Locate the subcategory header (some pages use h3, some use h2)
        header = page.locator("h3", has_text=title)
        if await header.count() == 0:
            header = page.locator("h2", has_text=title)
        if await header.count() == 0:
            # Fallback to match prefix before colon (e.g., "Evals: domains..." -> "Evals")
            prefix = title.split(":")[0].strip()
            header = page.locator("h3", has_text=prefix)
        if await header.count() == 0:
            # Can't find header — skip rubric for this one
            rubrics[title] = {"description": None, "description_html": None}
            continue

        h = header.first
        with suppress(Exception):
            await h.scroll_into_view_if_needed()

        # Find and click the nearest toggle labelled "Click to show details/rubric" (or "hide" if already open)
        toggle = h.locator(
            "xpath=following::*[self::button or self::div or self::span][contains(., 'Click to show details/rubric')][1]"
        )
        if await toggle.count() == 0:
            toggle = h.locator(
                "xpath=following::*[self::button or self::div or self::span][contains(., 'Click to hide details/rubric')][1]"
            )

        if await toggle.count() == 0:
            # As a fallback, try role-based search near the header
            near = h.locator("xpath=following::*[position()<=12]")
            btn = near.get_by_role(
                "button", name=re.compile(r"Click to (show|hide) details/rubric", re.I)
            )
            if await btn.count() > 0:
                toggle = btn.first

        try:
            await toggle.first.click(timeout=3000)
        except Exception:
            pass  # maybe already expanded or not a button

        # The rubric content should now be visible near the header
        rubric_div = h.locator(
            "xpath=following::*[contains(@class, 'text-sm') and contains(@class, 'links')][1]"
        )
        try:
            await rubric_div.wait_for(state="visible", timeout=5000)
            html = await rubric_div.inner_html()
            text = await rubric_div.inner_text()
            rubrics[title] = {"description": text, "description_html": html}
        except PWTimeout:
            # Global fallback: first rubric-like div on page (last resort)
            global_div = page.locator("css=div.text-sm.links").first
            if await global_div.count():
                html = await global_div.inner_html()
                text = await global_div.inner_text()
                rubrics[title] = {"description": text, "description_html": html}
            else:
                rubrics[title] = {"description": None, "description_html": None}

    await page.close()
    return rubrics


async def build_dataset() -> List[Dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()

        # 1) Category weights from overview page
        cat_weights = await get_category_weights(context)

        out: List[Dict] = []

        # 2) For each category: subcategory weights/scores + rubric
        for slug, title in CATEGORIES:
            print(f"Scraping {title}…", file=sys.stderr)
            subcats = await parse_category_page(context, slug)
            rubrics = await scrape_subcategory_rubrics(context, slug, subcats)

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
    path = Path("ailabwatch_categories_subcategories_scores_weights.json")
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(str(path.resolve()))


if __name__ == "__main__":
    main()
