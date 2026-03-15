"""
Scrape les fiches métier ROME depuis France Travail.

Deux modes :
  - API REST France Travail (recommandé, nécessite FRANCE_TRAVAIL_CLIENT_ID
    et FRANCE_TRAVAIL_CLIENT_SECRET dans .env)
  - Scraping HTML via Playwright (fallback si pas de credentials API)

Sauvegarde le HTML brut dans html_fr/<slug>.html.

Usage:
    uv run python scrape_fr.py                        # tout scraper
    uv run python scrape_fr.py --start 0 --end 5      # premiers 5
    uv run python scrape_fr.py --mode api              # forcer mode API
    uv run python scrape_fr.py --mode html             # forcer mode HTML
"""

import argparse
import json
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

HTML_DIR = "html_fr"
OCCUPATIONS_FILE = "occupations_fr.json"


# ---------------------------------------------------------------------------
# Mode API : France Travail (ex-Emploi Store)
# ---------------------------------------------------------------------------

def get_access_token():
    """Obtenir un token OAuth2 depuis l'API France Travail."""
    client_id = os.environ.get("FRANCE_TRAVAIL_CLIENT_ID")
    client_secret = os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    resp = httpx.post(
        "https://entreprise.francetravail.fr/connexion/oauth2/access_token",
        params={"realm": "/partenaire"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": "api_rome-metiersv1 nomenclatureRome",
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def scrape_api(occupations, args):
    """Scraper les fiches via l'API REST France Travail."""
    token = get_access_token()
    if not token:
        print("ERREUR : FRANCE_TRAVAIL_CLIENT_ID / CLIENT_SECRET manquants dans .env")
        print("Basculer vers --mode html ou configurer les credentials.")
        return

    client = httpx.Client()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    for i, occ in enumerate(occupations):
        slug = occ["slug"]
        code = occ["code_rome"]
        out_path = os.path.join(HTML_DIR, f"{slug}.json")

        if not args.force and os.path.exists(out_path):
            print(f"  [{i}] CACHE {occ['title']}")
            continue

        print(f"  [{i}/{len(occupations)}] {occ['title']} ({code})...", end=" ", flush=True)

        try:
            # Fiche métier complète
            resp = client.get(
                f"https://api.francetravail.io/partenaire/rome/v1/metier/{code}",
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()

            with open(out_path, "w") as f:
                json.dump(resp.json(), f, ensure_ascii=False, indent=2)

            print("OK")
        except Exception as e:
            print(f"ERREUR: {e}")

        if i < len(occupations) - 1:
            time.sleep(args.delay)

    client.close()


# ---------------------------------------------------------------------------
# Mode HTML : scraping Playwright
# ---------------------------------------------------------------------------

def scrape_html(occupations, args):
    """Scraper les fiches ROME depuis le site France Travail via Playwright."""
    from playwright.sync_api import sync_playwright

    to_scrape = []
    for i, occ in enumerate(occupations):
        html_path = os.path.join(HTML_DIR, f"{occ['slug']}.html")
        if not args.force and os.path.exists(html_path):
            print(f"  [{i}] CACHE {occ['title']}")
            continue
        to_scrape.append((i, occ))

    if not to_scrape:
        print("Rien à scraper — tout est en cache.")
        return

    print(f"\nScraping {len(to_scrape)} fiches (Chromium non-headless)...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        for idx, (i, occ) in enumerate(to_scrape):
            slug = occ["slug"]
            url = occ["url"]
            html_path = os.path.join(HTML_DIR, f"{slug}.html")

            print(f"  [{i}] {occ['title']}...", end=" ", flush=True)

            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
                if resp.status != 200:
                    print(f"HTTP {resp.status} — IGNORE")
                    continue

                html = page.content()
                with open(html_path, "w") as f:
                    f.write(html)

                print(f"OK ({len(html):,} octets)")
            except Exception as e:
                print(f"ERREUR: {e}")

            if idx < len(to_scrape) - 1:
                time.sleep(args.delay)

        browser.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scraper fiches ROME France Travail")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--force", action="store_true", help="Re-scraper même si en cache")
    parser.add_argument("--delay", type=float, default=1.0, help="Délai entre requêtes (sec)")
    parser.add_argument("--mode", choices=["api", "html", "auto"], default="auto",
                        help="Mode: api (REST), html (Playwright), auto (API si credentials)")
    args = parser.parse_args()

    with open(OCCUPATIONS_FILE) as f:
        all_occupations = json.load(f)

    end = args.end if args.end is not None else len(all_occupations)
    occupations = all_occupations[args.start:end]

    os.makedirs(HTML_DIR, exist_ok=True)

    # Choix du mode
    mode = args.mode
    if mode == "auto":
        has_creds = (os.environ.get("FRANCE_TRAVAIL_CLIENT_ID") and
                     os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET"))
        mode = "api" if has_creds else "html"

    print(f"Mode : {mode.upper()}")
    print(f"Fiches : {len(occupations)}")

    if mode == "api":
        scrape_api(occupations, args)
    else:
        scrape_html(occupations, args)

    # Résumé
    cached = len([f for f in os.listdir(HTML_DIR)
                  if f.endswith(".html") or f.endswith(".json")])
    print(f"\nTerminé. {cached}/{len(all_occupations)} fiches en cache dans {HTML_DIR}/")


if __name__ == "__main__":
    main()
