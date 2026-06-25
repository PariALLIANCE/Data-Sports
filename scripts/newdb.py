import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright

TARGET_URL = "https://www.espn.com/soccer/team/results/_/id/6272/season/2025"
OUTPUT_FILE = "results.json"

async def scrape_espn_results():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await context.new_page()

        print(f"→ Chargement de {TARGET_URL}")
        await page.goto(TARGET_URL, wait_until="networkidle", timeout=60_000)

        await page.wait_for_selector(".Table__results-mobile", timeout=30_000)

        matches = []

        month_blocks = await page.query_selector_all(".Table__results-mobile")
        print(f"→ {len(month_blocks)} bloc(s) mensuel(s) trouvé(s)")

        for block in month_blocks:
            title_el = await block.query_selector(".Table__Title")
            month_label = await title_el.inner_text() if title_el else "Unknown"

            rows = await block.query_selector_all("tbody.Table__TBODY tr.Table__TR--sm")

            for row in rows:
                try:
                    match = await parse_row(row, month_label)
                    if match:
                        matches.append(match)
                        print(
                            f"  ✓ {match['date']} | {match['home_team']} "
                            f"{match['home_score']}-{match['away_score']} "
                            f"{match['away_team']} | {match['competition']}"
                        )
                except Exception as e:
                    print(f"  ✗ Erreur sur une ligne : {e}")

        await browser.close()

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(matches, f, ensure_ascii=False, indent=2)

        print(f"\n✅ {len(matches)} match(s) exporté(s) dans '{OUTPUT_FILE}'")
        return matches


async def parse_row(row, month_label: str) -> dict | None:
    cells = await row.query_selector_all("td.Table__TD")
    if len(cells) < 6:
        return None

    # ── DATE ──────────────────────────────────────────────────────────────────
    date_el = await cells[0].query_selector("[data-testid='date']")
    raw_date = await date_el.inner_text() if date_el else ""
    year_match = re.search(r"\d{4}", month_label)
    year = year_match.group(0) if year_match else str(datetime.now().year)
    date_str = f"{raw_date.strip()}, {year}"

    # ── ÉQUIPES ───────────────────────────────────────────────────────────────
    home_el = await cells[1].query_selector("[data-testid='formattedTeam']")
    away_el = await cells[3].query_selector("[data-testid='formattedTeam']")

    home_href = await home_el.get_attribute("href") if home_el else ""
    away_href = await away_el.get_attribute("href") if away_el else ""

    home_name = _name_from_href(home_href)
    away_name = _name_from_href(away_href)
    home_id = _id_from_href(home_href)
    away_id = _id_from_href(away_href)

    # ── CELLULE SCORE ─────────────────────────────────────────────────────────
    score_cell = await cells[2].query_selector("[data-testid='score']")
    score_links = await score_cell.query_selector_all("a.AnchorLink") if score_cell else []

    home_logo_url = ""
    away_logo_url = ""
    home_score = ""
    away_score = ""
    match_url = ""

    if len(score_links) >= 3:
        img_home = await score_links[0].query_selector("img")
        if img_home:
            home_logo_url = await img_home.get_attribute("src") or ""

        score_text = (await score_links[1].inner_text()).strip()
        rel_match_url = await score_links[1].get_attribute("href") or ""
        match_url = _absolute(rel_match_url)
        home_score, away_score = _parse_score(score_text)

        img_away = await score_links[2].query_selector("img")
        if img_away:
            away_logo_url = await img_away.get_attribute("src") or ""

    # ── RÉSULTAT (FT / AET / PEN …) ──────────────────────────────────────────
    result_el = await cells[4].query_selector("[data-testid='result'] a")
    result_status = await result_el.inner_text() if result_el else ""

    # ── COMPÉTITION ───────────────────────────────────────────────────────────
    comp_el = await cells[5].query_selector("span")
    competition = await comp_el.inner_text() if comp_el else ""

    return {
        "date": date_str,
        "month_block": month_label,
        "home_team": home_name,
        "home_id": home_id,
        "home_score": home_score,
        "away_score": away_score,
        "away_team": away_name,
        "away_id": away_id,
        "result_status": result_status,
        "competition": competition,
        "home_logo_url": home_logo_url,
        "away_logo_url": away_logo_url,
        "match_url": match_url,
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _id_from_href(href: str) -> str:
    """
    Extrait l'ID numérique ESPN depuis un href.
    Ex: /soccer/team/_/id/6086/botafogo  →  "6086"
    """
    if not href:
        return ""
    m = re.search(r"/id/(\d+)/", href)
    return m.group(1) if m else ""


def _name_from_href(href: str) -> str:
    """
    Extrait le nom depuis le slug ESPN.
    Ex: /soccer/team/_/id/6086/botafogo  →  "Botafogo"
    """
    if not href:
        return ""
    parts = href.rstrip("/").split("/")
    return parts[-1].replace("-", " ").title() if parts else ""


def _absolute(href: str) -> str:
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return f"https://www.espn.com{href}"


def _parse_score(score_text: str) -> tuple[str, str]:
    m = re.search(r"(\d+)\s*-\s*(\d+)", score_text)
    if m:
        return m.group(1), m.group(2)
    return "", ""


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    asyncio.run(scrape_espn_results())