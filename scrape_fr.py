"""
Scrape les fiches métier ROME depuis France Travail.

Deux modes :
  - API REST France Travail (recommandé, nécessite FRANCE_TRAVAIL_CLIENT_ID
    et FRANCE_TRAVAIL_CLIENT_SECRET dans .env)
  - Scraping HTML via Playwright (fallback si pas de credentials API)

Sauvegarde le HTML brut dans html_fr/<slug>.html.

Rate limits France Travail :
  - ROME 4.0 Métiers / Fiches / Compétences : 1 appel/sec
  - Marché du travail : 10 appels/sec

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

# Rate limits par API (en secondes entre chaque appel)
RATE_LIMITS = {
    "rome_metiers": 1.1,       # ROME 4.0 Métiers v1 : 1 appel/sec → 1.1s marge
    "rome_fiches": 1.1,        # ROME 4.0 Fiches métiers v1 : 1 appel/sec
    "rome_competences": 1.1,   # ROME 4.0 Compétences v1 : 1 appel/sec
    "marche_travail": 0.15,    # Marché du travail v1 : 10 appels/sec → 0.15s marge
}

# Suivi des derniers appels par API pour respecter les rate limits
_last_call = {}


def rate_limit_wait(api_name):
    """Attendre le temps nécessaire pour respecter le rate limit d'une API."""
    min_interval = RATE_LIMITS.get(api_name, 1.1)
    now = time.monotonic()
    last = _last_call.get(api_name, 0)
    elapsed = now - last
    if elapsed < min_interval:
        wait = min_interval - elapsed
        time.sleep(wait)
    _last_call[api_name] = time.monotonic()


def api_call_with_retry(client, url, headers, api_name, max_retries=3):
    """Appel API avec respect du rate limit et retry sur 429."""
    for attempt in range(max_retries + 1):
        rate_limit_wait(api_name)
        try:
            resp = client.get(url, headers=headers, timeout=15)
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", 2))
                wait = max(retry_after, RATE_LIMITS.get(api_name, 1.1) * 2)
                print(f"429 rate limit, attente {wait:.1f}s...", end=" ", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as e:
            if attempt < max_retries:
                wait = 2 ** (attempt + 1)
                print(f"erreur réseau, retry dans {wait}s...", end=" ", flush=True)
                time.sleep(wait)
            else:
                raise
    return None


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
            "scope": " ".join([
                "api_rome-metiersv1",
                "api_rome-fichesv1",
                "api_rome-competencesv1",
                "api_marchedutravailv1",
                "nomenclatureRome",
            ]),
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def scrape_api(occupations, args):
    """Scraper les fiches via l'API REST France Travail (rate-limited)."""
    token = get_access_token()
    if not token:
        print("ERREUR : FRANCE_TRAVAIL_CLIENT_ID / CLIENT_SECRET manquants dans .env")
        print("Basculer vers --mode html ou configurer les credentials.")
        return

    client = httpx.Client()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    print(f"\nRate limits : ROME=1 req/s, Marché du travail=10 req/s")
    print(f"Temps estimé : ~{len(occupations) * 3.5:.0f}s "
          f"({len(occupations)} métiers × ~3.5s/métier)\n")

    for i, occ in enumerate(occupations):
        slug = occ["slug"]
        code = occ["code_rome"]
        out_path = os.path.join(HTML_DIR, f"{slug}.json")

        if not args.force and os.path.exists(out_path):
            print(f"  [{i}] CACHE {occ['title']}")
            continue

        print(f"  [{i}/{len(occupations)}] {occ['title']} ({code})...", end=" ", flush=True)

        try:
            result = {}

            # 1. Fiche métier (ROME Fiches : 1 req/s)
            resp = api_call_with_retry(
                client,
                f"https://api.francetravail.io/partenaire/rome-fiches/v1/fichemetier/{code}",
                headers, "rome_fiches",
            )
            if resp:
                result["fiche"] = resp.json()

            # 2. Métier info (ROME Métiers : 1 req/s)
            resp = api_call_with_retry(
                client,
                f"https://api.francetravail.io/partenaire/rome-metiers/v1/metiers/metier/{code}",
                headers, "rome_metiers",
            )
            if resp:
                result["metier"] = resp.json()

            # 3. Stats marché du travail (10 req/s — plus rapide)
            resp = api_call_with_retry(
                client,
                f"https://api.francetravail.io/partenaire/marche-travail/v1/statistiques/rome/{code}",
                headers, "marche_travail",
            )
            if resp:
                result["marche"] = resp.json()

            with open(out_path, "w") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            print("OK")
        except Exception as e:
            print(f"ERREUR: {e}")

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
        print("(rate limits gérés automatiquement, --delay ignoré en mode API)")
        scrape_api(occupations, args)
    else:
        scrape_html(occupations, args)

    # Résumé
    cached = len([f for f in os.listdir(HTML_DIR)
                  if f.endswith(".html") or f.endswith(".json")])
    print(f"\nTerminé. {cached}/{len(all_occupations)} fiches en cache dans {HTML_DIR}/")


if __name__ == "__main__":
    main()
