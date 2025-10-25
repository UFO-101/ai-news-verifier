# ailabwatch_full_scraper_v8.py
# --------------------------------
# Requirements:
#   pip install playwright
#   playwright install
#
# Run:
#   python ailabwatch_full_scraper_v8.py
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
COMPANY_SLUG = {
    "Anthropic": "anthropic",
    "DeepMind": "deepmind",
    "OpenAI": "openai",
    "Meta": "meta",
    "xAI": "xai",
    "Microsoft": "microsoft",
    "DeepSeek": "deepseek",
}


async def get_category_weights(page: Page) -> Dict[str, Optional[int]]:
    """Parse 'NN % weight' for each category on the overview page."""
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


async def parse_category_page(page: Page, slug: str) -> List[Dict]:
    """
    For a category page, return list of subcats with:
      - subcategory weight ("Weighted NN% of category")
      - per-company scores (by DOM evaluation inside the page)
    """
    await page.goto(urljoin(BASE, f"categories/{slug}"), wait_until="domcontentloaded")
    with suppress(PWTimeout):
        await page.wait_for_selector("h2", timeout=8000)

    # JS helper to extract weight near a given <h2>
    get_weight_js = """
    (h2) => {
      // Scan a few following siblings for "Weighted NN% of category"
      let n = h2.nextElementSibling;
      for (let i=0; i<8 && n; i++, n = n.nextElementSibling) {
        const t = (n.innerText || '').trim();
        const m = t.match(/Weighted\\s+(\\d+)%\\s+of category/i);
        if (m) return parseInt(m[1], 10);
      }
      return null;
    }
    """

    # JS helper to compute per-company scores in the region between this h2 and the next h2.
    # Strategy:
    # 1) Build a detached container with all nodes between <h2> and the next <h2>.
    # 2) For each company, find <a href*="/cell/<company>/<category>"> anchors inside that region.
    # 3) For each anchor, walk up to a likely "card" container; scan its textContent for "NN%".
    # 4) If not found, scan a few next siblings. If still not found, scan the anchor text itself.
    extract_scores_js = """
    (h2, categorySlug, companySlugMap) => {
      // 1) collect region nodes
      const regionNodes = [];
      let n = h2.nextElementSibling;
      while (n && n.tagName !== 'H2') { regionNodes.push(n); n = n.nextElementSibling; }

      // Build a detached region to query reliably without affecting layout
      const region = document.createElement('div');
      for (const el of regionNodes) region.appendChild(el.cloneNode(true));

      const scores = {};
      const percentRe = /(\\d+)\\s*%/;

      const companies = Object.keys(companySlugMap);
      for (const company of companies) {
        const cslug = companySlugMap[company];
        let val = null;

        // 2) anchors inside region
        const anchors = region.querySelectorAll(`a[href*="/cell/${cslug}/${categorySlug}"]`);
        for (const a of anchors) {
          // 3) climb to a "card-ish" container and scan for % text
          const isCardish = (el) => {
            if (!el || !el.classList) return false;
            const c = (el.className || "").toLowerCase();
            return c.includes('card') || c.includes('grid') || c.includes('panel') || c.includes('tile') || c.includes('item');
          };
          let container = a;
          for (let i=0; i<6 && container; i++) {
            if (isCardish(container)) break;
            container = container.parentElement;
          }
          if (!container) container = a.closest('a, div, li, article, section') || a.parentElement || a;

          const tryNode = (el) => {
            const text = (el && el.textContent) ? el.textContent : '';
            const m = text.match(percentRe);
            return m ? parseInt(m[1], 10) : null;
          };

          // scan container
          val = tryNode(container);
          if (val != null) break;

          // scan a few next siblings
          let sib = container.nextElementSibling;
          for (let j=0; j<4 && sib && val == null; j++, sib = sib.nextElementSibling) {
            val = tryNode(sib);
          }
          if (val != null) break;

          // last resort: scan the anchor itself
          val = tryNode(a);
          if (val != null) break;
        }

        scores[company] = val;
      }
      return scores;
    }
    """

    subcats: List[Dict] = []

    headers: Locator = page.locator("h2")
    count = await headers.count()
    for i in range(count):
        header = headers.nth(i)
        name = (await header.inner_text()).strip()
        if not name:
            continue

        # subcategory weight
        weight = await page.evaluate(get_weight_js, await header.element_handle())

        # per-company scores in this region (fully in-page evaluation)
        scores = await page.evaluate(
            extract_scores_js, await header.element_handle(), slug, COMPANY_SLUG
        )

        subcats.append({"name": name, "weight": weight, "scores": scores})

    return subcats


async def click_near_toggle(header: Locator) -> None:
    """Click the nearest rubric toggle after the given header (h2/h3),
    matching both 'show' and 'hide' variants."""
    toggle = header.locator(
        "xpath=following::*[self::button or self::div or self::span]"
        "[contains(., 'Click to show details/rubric') or contains(., 'Click to hide details/rubric')][1]"
    )
    try:
        if await toggle.count():
            await toggle.first.click(timeout=3000)
    except Exception:
        pass  # it may already be expanded


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
            # global fallback
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

        # 2) For each category: subcategories + scores + rubrics
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
