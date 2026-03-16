"""
Récupère la liste complète des codes ROME depuis l'API France Travail
et génère occupations_fr.json avec tous les métiers (~530 fiches).

Utilise les endpoints ROME 4.0 :
  - /metiers/grand-domaine → 14 grands domaines
  - /metiers/domaine-professionnel → ~100 domaines professionnels
  - /metiers/metier → ~530 fiches métier

Usage:
    uv run python fetch_all_rome.py
    uv run python fetch_all_rome.py --output occupations_fr_full.json
"""

import argparse
import json
import os
import re
import time
import unicodedata

import httpx
from dotenv import load_dotenv

load_dotenv()


def get_access_token():
    """Obtenir un token OAuth2 depuis l'API France Travail."""
    client_id = os.environ.get("FRANCE_TRAVAIL_CLIENT_ID")
    client_secret = os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET")
    if not client_id or not client_secret:
        print("ERREUR : FRANCE_TRAVAIL_CLIENT_ID / CLIENT_SECRET manquants dans .env")
        raise SystemExit(1)

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


def slugify(text):
    """Convertir un titre en slug URL-friendly."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text


def api_get(client, url, headers, retries=3):
    """GET avec retry et rate limit (ROME API : 1 req/s)."""
    for attempt in range(retries + 1):
        try:
            time.sleep(1.1)
            resp = client.get(url, headers=headers, timeout=15)
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", 3))
                print(f"  429, attente {wait}s...", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
            else:
                raise
    return None


def main():
    parser = argparse.ArgumentParser(description="Récupérer tous les codes ROME")
    parser.add_argument("--output", default="occupations_fr.json")
    args = parser.parse_args()

    print("Authentification OAuth2...")
    token = get_access_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    client = httpx.Client()

    BASE = "https://api.francetravail.io/partenaire/rome-metiers/v1/metiers"

    # 1. Grands domaines (14)
    print("Grands domaines...")
    domains_data = api_get(client, f"{BASE}/grand-domaine", headers)
    domain_map = {}
    if domains_data:
        for d in domains_data:
            domain_map[d["code"]] = d["libelle"]
        print(f"  {len(domain_map)} grands domaines")
    else:
        print("  WARN: impossible de recuperer les grands domaines")

    # 2. Domaines professionnels (~100)
    print("Domaines professionnels...")
    subdomains_data = api_get(client, f"{BASE}/domaine-professionnel", headers)
    subdomain_map = {}
    if subdomains_data:
        for d in subdomains_data:
            subdomain_map[d["code"]] = d["libelle"]
        print(f"  {len(subdomain_map)} domaines professionnels")

    # 3. Tous les metiers (~530)
    print("Metiers...")
    metiers_data = api_get(client, f"{BASE}/metier", headers)
    if not metiers_data:
        print("ERREUR : impossible de recuperer la liste des metiers")
        raise SystemExit(1)

    print(f"  {len(metiers_data)} metiers trouves")

    # 4. Construire occupations_fr.json
    occupations = []
    for m in metiers_data:
        code = m["code"]
        title = m["libelle"]
        domain_code = code[0]
        subdomain_code = code[:3] if len(code) >= 3 else code

        occupations.append({
            "title": title,
            "code_rome": code,
            "slug": slugify(title),
            "domain_code": domain_code,
            "domain_name": domain_map.get(domain_code, domain_code),
            "subdomain_code": subdomain_code,
            "subdomain_name": subdomain_map.get(subdomain_code, subdomain_code),
            "category": slugify(domain_map.get(domain_code, domain_code)),
            "url": f"https://candidat.francetravail.fr/marche-du-travail/fichemetierrome?codeRome={code}",
        })

    occupations.sort(key=lambda x: x["code_rome"])

    with open(args.output, "w") as f:
        json.dump(occupations, f, ensure_ascii=False, indent=2)

    print(f"\n{len(occupations)} metiers ecrits dans {args.output}")
    print(f"  {len(domain_map)} grands domaines")
    print(f"  {len(subdomain_map)} domaines professionnels")

    client.close()


if __name__ == "__main__":
    main()
