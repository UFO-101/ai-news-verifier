# ailabwatch_full_scraper_v7.py
# --------------------------------
# Requirements:
#   pip install playwright
#   playwright install
#
# Run:
#   python ailabwatch_full_scraper_v7.py
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

from playwright.async_api import ElementHandle, Locator, Page, async_playwright
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
COMPANY_SLUG = {
    "Anthropic": "anthropic",
    "DeepMind": "deepmind",
    "OpenAI": "openai",
    "Meta": "meta",
    "xAI": "xai",
    "Microsoft": "microsoft",
    "DeepSeek": "deepseek",
}

PERCENT_RE = re.compile(r"(\d+)\s*%")


async def get_category_weights(page: Page) -> Dict[str, Optional[int]]:
    await page.goto(urljoin(BASE, "categories"), wait_until="domcontentloaded")
    with suppress(PWTimeout):
        await page.wait_for_selector("h1, h2, a", timeout=8000)
    body_text = await page.locator("body").inner_text()
    weights: Dict[str, Optional[int]] = {}
    for slug, title in CATEGORIES:
        m = re.search(
            re.escape(title) + r".{0,300}?(\d+)\s*%\s*weight",
            body_text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        weights[title] = int(m.group(1)) if m else None
    return weights


async def _slice_elements_between_h2s(
    page: Page, header: Locator
) -> List[ElementHandle]:
    """Return a list of element handles between this <h2> and the next <h2>."""
    return (
        await page.evaluate_handle(
            """(h2) => {
            const out = [];
            let n = h2.nextElementSibling;
            while (n && n.tagName !== 'H2') {
                out.push(n);
                n = n.nextElementSibling;
            }
            return out;
        }""",
            await header.element_handle(),
        )
        .get_properties()
        .then(lambda m: [v for v in m.values()])
    )


async def _region_query_selector_all(
    page: Page, header: Locator, selector: str
) -> List[ElementHandle]:
    """Query elements within the region (between this <h2> and the next <h2>)."""
    # Grab nodes in region and query inside each
    nodes = await _slice_elements_between_h2s(page, header)
    results: List[ElementHandle] = []
    for node in nodes:
        # Query inside this node
        handles = await page.query_selector_all(f":scope >>> :is({selector})")
        # Above line queries whole document; limit to subtree via JS:
        sub = await page.evaluate_handle(
            """(root, sel) => Array.from(root.querySelectorAll(sel))""", node, selector
        )
        props = await sub.get_properties()
        results.extend([v for v in props.values()])
    return results


async def _extract_scores_from_region(
    page: Page, header: Locator, category_slug: str
) -> Dict[str, Optional[int]]:
    """Find per-company scores by locating the anchor to /cell/<company>/<category>,
    then scanning its nearest card container's text for 'NN%'. Fallback: scan adjacent siblings."""
    scores: Dict[str, Optional[int]] = {c: None for c in COMPANIES}

    # Collect all anchors in the region once
    anchors = await _region_query_selector_all(page, header, "a[href]")
    # Build a map from company -> list of matching anchors in this region
    comp_anchors: Dict[str, List[ElementHandle]] = {c: [] for c in COMPANIES}

    for a in anchors:
        href = await a.get_attribute("href")
        if not href:
            continue
        for company, cslug in COMPANY_SLUG.items():
            # Match anchors that include the company slug and (ideally) the current category slug
            if f"/cell/{cslug}/" in href and category_slug in href:
                comp_anchors[company].append(a)

    # Helper that scans a DOM node's text for NN%
    async def scan_for_percent(node: ElementHandle) -> Optional[int]:
        txt = (await node.inner_text()).strip()
        m = PERCENT_RE.search(txt)
        return int(m.group(1)) if m else None

    # For each company, try: same anchor -> closest card container -> siblings
    for company in COMPANIES:
        if not comp_anchors[company]:
            continue
        anchor = comp_anchors[company][0]

        # 1) Try closest card container
        card = await page.evaluate_handle(
            """(a) => {
                // Walk up to a likely card container
                const isCard = (el) => {
                    if (!el || !el.classList) return false;
                    const c = el.className.toLowerCase();
                    return c.includes('card') || c.includes('item') or c.includes('grid') || c.includes('tile') || c.includes('panel');
                };
                let n = a;
                for (let i=0; i<5 && n; i++) {
                    if (isCard(n)) return n;
                    n = n.parentElement;
                }
                // Fallback: <a> itself or its parent
                return a.closest('a, div, li, article, section') || a.parentElement || a;
            }""",
            anchor,
        )
        val = await scan_for_percent(card)
        if val is not None:
            scores[company] = val
            continue

        # 2) Try a few next siblings from the card
        try:
            sib_score = await page.evaluate_handle(
                """(root) => {
                    let n = root.nextElementSibling;
                    for (let i=0;i<4 && n;i++){
                        const t = n.textContent || '';
                        const m = t.match(/(\\d+)\\s*%/);
                        if (m) return parseInt(m[1], 10);
                        n = n.nextElementSibling;
                    }
                    return null;
                }""",
                card,
            )
            if sib_score:
                scores[company] = int(await sib_score.json_value())
                continue
        except Exception:
            pass

        # 3) Last resort: scan the anchor itself
        val = await scan_for_percent(anchor)
        if val is not None:
            scores[company] = val

    return scores


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

        # Scores by robust DOM probing inside the subcategory region
        scores = await _extract_scores_from_region(page, header, slug)

        subcats.append({"name": name, "weight": weight, "scores": scores})

    return subcats


async def click_near_toggle(header: Locator) -> None:
    toggle = header.locator(
        "xpath=following::*[self::button or self::div or self::span]"
        "[contains(., 'Click to show details/rubric') or contains(., 'Click to hide details/rubric')][1]"
    )
    try:
        if await toggle.count():
            await toggle.first.click(timeout=3000)
    except Exception:
        pass


async def scrape_subcategory_rubrics(
    page: Page, slug: str, subcats: List[Dict]
) -> Dict[str, Dict[str, Optional[str]]]:
    await page.goto(urljoin(BASE, f"cell/xai/{slug}"), wait_until="domcontentloaded")
    with suppress(PWTimeout):
        await page.wait_for_selector("h3, h2", timeout=8000)

    rubrics: Dict[str, Dict[str, Optional[str]]] = {}
    for sc in subcats:
        title = sc["name"]

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

        rubric_div = h.locator(
            "xpath=following::*[contains(@class, 'text-sm') and contains(@class, 'links')][1]"
        )
        try:
            await rubric_div.wait_for(state="visible", timeout=5000)
            html = await rubric_div.inner_html()
            text = await rubric_div.inner_text()
            rubrics[title] = {"description": text, "description_html": html}
        except PWTimeout:
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

        # 1) Category weights
        page1 = await context.new_page()
        cat_weights = await get_category_weights(page1)
        await page1.close()

        out: List[Dict] = []

        # 2) For each category: subcategory + scores + rubric
        for slug, title in CATEGORIES:
            print(f"Scraping {title}…", file=sys.stderr)

            page2 = await context.new_page()
            subcats = await parse_category_page(page2, slug)
            await page2.close()

            page3 = await context.new_page()
            rubrics = await scrape_subcategory_rubrics(page3, slug, subcats)
            await page3.close()

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
