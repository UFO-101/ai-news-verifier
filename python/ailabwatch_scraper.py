
import asyncio, json, re, sys
from pathlib import Path
from urllib.parse import urljoin
from typing import Dict, List
try:
    from playwright.async_api import async_playwright
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
    """Scrape the category page and extract per-subcategory weights + per-company scores.
    Then, for each subcategory, open a representative company 'cell' page to read the rubric
    (the rubric content is behind a JS toggle and is identical across companies for a given subcategory)."""
    page = await context.new_page()
    url = urljoin(BASE, f"categories/{slug}")
    await page.goto(url, wait_until="domcontentloaded")
    # Wait for headings to render
    await page.wait_for_selector("h1, h2")

    # Parse subcategory sections
    subcats = []
    # Each subcategory is rendered as an h2 followed by a 'Weighted ...' line and a grid of company blocks.
    h2s = await page.locator("h2").all_inner_texts()
    # Filter out page-level headings like "Risk assessment"
    # We'll iterate DOM instead of just texts to keep order and extract around each h2 node.
    nodes = page.locator("h2")
    count = await nodes.count()
    for i in range(count):
        name = (await nodes.nth(i).inner_text()).strip()
        if not name or name.startswith("##"):
            continue
        # Exclude the page title which is an h1 (we only iterate h2 anyway)
        # The weight is near text 'Weighted NN% of category' in following sibling
        section = nodes.nth(i)
        # Find the 'Weighted' line nearby
        weight = None
        # Search within the next 8 siblings for 'Weighted'
        for j in range(1, 8):
            sibling = section.locator(f"xpath=following::*[{j}]")
            try:
                txt = (await sibling.inner_text()).strip()
            except:
                continue
            m = re.search(r"Weighted\s+(\d+)%\s+of category", txt)
            if m:
                weight = int(m.group(1))
                break

        # Extract per-company scores by reading "Image: Company" cards' percentage
        scores = {}
        # Cards have the company icon followed by a % number
        # Use a conservative approach: search the following section until the next h2
        # Collect all text content in that span and parse "Company\nNN%"
        start = await section.evaluate_handle("el => el")
        next_h2 = await page.evaluate_handle("""(el) => {
            let n = el.nextElementSibling;
            while (n && n.tagName !== 'H2') n = n.nextElementSibling;
            return n || null;
        }""", start)
        # Get the text slice between this h2 and next h2 (or end of page)
        end_locator = page.locator("h2").nth(i+1) if i+1 < count else None
        span = section.locator("xpath=following-sibling::*")
        span_count = await span.count()
        collected = []
        for k in range(span_count):
            # Stop at next h2
            tag = await span.nth(k).evaluate("n => n.tagName")
            if tag == "H2":
                break
            collected.append((await span.nth(k).inner_text()).strip())

        joined = "\n".join(collected)
        for comp in COMPANIES:
            # Look for a pattern like: "Image: {comp}\nNN%"
            m = re.search(rf"Image:\s*{re.escape(comp)}\s*\n(\d+)%", joined)
            if m:
                scores[comp] = int(m.group(1))

        subcats.append({"name": name, "weight": weight, "official_scores": scores})

    # For rubric text per subcategory, open any 'cell' page and click the rubric toggle under that subcategory.
    # We'll use xAI as the representative company because its cell pages list all subcategories.
    cell_page = await context.new_page()
    cell_url = urljoin(BASE, f"cell/xai/{slug}")
    await cell_page.goto(cell_url, wait_until="domcontentloaded")
    await cell_page.wait_for_selector("h3, h2, text=Click to show details/rubric")

    # Map: subcategory name -> rubric html/text
    rubrics = {}
    for sc in subcats:
        # The rubric toggle should appear under an h3 with the same subcategory title
        # Try to locate the h3 by exact text (strip punctuation/extra spaces first).
        title = sc["name"]
        # Find the 'Click to show details/rubric' that is the next sibling under this h3 and click it.
        h3 = cell_page.locator("h3", has_text=title)
        if await h3.count() == 0:
            # Fallback: try starts-with match
            h3 = cell_page.locator("h3", has_text=title.split(":")[0])
        if await h3.count() == 0:
            continue
        # Scroll into view
        await h3.first.scroll_into_view_if_needed()
        # The toggle is the next element containing the clickable text
        toggle = h3.first.locator("xpath=following::button[contains(., 'Click to show details/rubric')][1]")
        if await toggle.count() == 0:
            # Sometimes it's a <div> or <span>
            toggle = h3.first.locator("xpath=following::*[contains(., 'Click to show details/rubric')][1]")
        await toggle.first.click()
        # After expansion, a div with class 'text-sm links' should appear nearby.
        rubric_div = h3.first.locator("xpath=following::*[contains(@class, 'text-sm') and contains(@class, 'links')][1]")
        await rubric_div.wait_for(timeout=5000)
        # Prefer HTML to preserve links; also capture plain text
        html = await rubric_div.inner_html()
        text = await rubric_div.inner_text()
        rubrics[title] = {"html": html, "text": text}

    # Merge rubrics into subcategories
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
            out[cat_name] = await extract_category(context, slug)
        await context.close()
        await browser.close()
    # Save
    path = Path("ailabwatch_subcategory_rubrics.json")
    with path.open("w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(path.resolve())

if __name__ == "__main__":
    asyncio.run(main())
