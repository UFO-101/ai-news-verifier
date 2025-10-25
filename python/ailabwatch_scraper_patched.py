
import asyncio, json, re, sys
from pathlib import Path
from urllib.parse import urljoin
from typing import Dict
from contextlib import suppress

try:
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout
except ImportError as e:
    print("Please install Playwright first: pip install playwright && playwright install", file=sys.stderr)
    raise

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

COMPANIES = ["Anthropic","DeepMind","OpenAI","Meta","xAI","Microsoft","DeepSeek"]

async def extract_category(context, slug: str) -> Dict:
    page = await context.new_page()
    url = urljoin(BASE, f"categories/{slug}")
    await page.goto(url, wait_until="domcontentloaded")
    # Some pages lazy-render, give them a tick
    with suppress(PWTimeout):
        await page.wait_for_selector("h1", timeout=5000)
    with suppress(PWTimeout):
        await page.wait_for_selector("h2", timeout=5000)

    # Gather subcategories
    subcats = []
    nodes = page.locator("h2")
    count = await nodes.count()
    for i in range(count):
        name = (await nodes.nth(i).inner_text()).strip()
        if not name:
            continue

        # Weight (lookahead a few nodes)
        weight = None
        for j in range(1, 10):
            sibling = nodes.nth(i).locator(f"xpath=following::*[{j}]")
            with suppress(Exception):
                txt = (await sibling.inner_text()).strip()
                m = re.search(r"Weighted\s+(\d+)%\s+of category", txt)
                if m:
                    weight = int(m.group(1))
                    break

        # Span text between this H2 and the next H2 -> parse per-company scores
        span = nodes.nth(i).locator("xpath=following-sibling::*")
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

        subcats.append({"name": name, "weight": weight, "official_scores": scores})

    # Rubrics (per-subcategory) — open a representative company "cell" page and expand each rubric
    cell_page = await context.new_page()
    cell_url = urljoin(BASE, f"cell/xai/{slug}")
    await cell_page.goto(cell_url, wait_until="domcontentloaded")
    # Wait separately for headers (CSS) and text (text=) to avoid the mixed-selector error
    with suppress(PWTimeout):
        await cell_page.wait_for_selector("h3, h2", timeout=8000)
    # Don't use "h3, h2, text=..." — Playwright treats that as a CSS selector. We'll wait for the text separately if needed.

    rubrics = {}
    for sc in subcats:
        title = sc["name"]
        # Locate the subcategory section header (some pages use h3, some use h2)
        header = cell_page.locator("h3", has_text=title)
        if await header.count() == 0:
            header = cell_page.locator("h2", has_text=title)
        if await header.count() == 0:
            # Try prefix before colon (e.g., "Evals: domains, quality, elicitation" -> "Evals")
            prefix = title.split(":")[0].strip()
            header = cell_page.locator("h3", has_text=prefix)
        if await header.count() == 0:
            continue

        h = header.first
        with suppress(Exception):
            await h.scroll_into_view_if_needed()

        # Find and click the nearest toggle labelled "Click to show details/rubric" (or "Click to hide…")
        toggle = h.locator("xpath=following::*[self::button or self::div or self::span][contains(., 'Click to show details/rubric')][1]")
        if await toggle.count() == 0:
            toggle = h.locator("xpath=following::*[self::button or self::div or self::span][contains(., 'Click to hide details/rubric')][1]")
        # As a fallback, try a role-based query within a reasonable DOM distance
        if await toggle.count() == 0:
            near = h.locator("xpath=following::*[position()<=10]")
            btn = near.get_by_role("button", name=re.compile("Click to (show|hide) details/rubric", re.I))
            if await btn.count() > 0:
                toggle = btn.first

        try:
            await toggle.first.click(timeout=3000)
        except Exception:
            pass  # It may already be expanded

        # The rubric content should now be visible near the header
        rubric_div = h.locator("xpath=following::*[contains(@class, 'text-sm') and contains(@class, 'links')][1]")
        try:
            await rubric_div.wait_for(state="visible", timeout=5000)
            html = await rubric_div.inner_html()
            text = await rubric_div.inner_text()
            rubrics[title] = {"html": html, "text": text}
        except PWTimeout:
            # Last-ditch: search globally for the first rubric block after the header
            global_div = cell_page.locator("css=div.text-sm.links").first
            if await global_div.count():
                html = await global_div.inner_html()
                text = await global_div.inner_text()
                rubrics[title] = {"html": html, "text": text}

    # Merge
    out = {}
    for sc in subcats:
        name = sc["name"]
        r = rubrics.get(name, {})
        out[name] = {
            "description_html": r.get("html"),
            "description": r.get("text"),
            "weight": sc["weight"],
            "official_scores": sc["official_scores"],
        }

    await page.close()
    await cell_page.close()
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
                print(f"[WARN] Failed on {cat_name}: {e}", file=sys.stderr)
                out[cat_name] = {}
        await context.close()
        await browser.close()
    path = Path("ailabwatch_subcategory_rubrics.json")
    with path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(path.resolve())

if __name__ == "__main__":
    asyncio.run(main())
