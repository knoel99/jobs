"""
Construit un CSV des métiers français à partir des fiches ROME scrapées.

Lit les fichiers html_fr/<slug>.html (ou .json si mode API), écrit occupations_fr.csv.

Les données salariales ne sont pas directement dans les fiches ROME.
Ce script extrait ce qui est disponible (niveau d'éducation, compétences)
et enrichit avec des données salariales si un fichier salaires_fr.csv existe.

Usage:
    uv run python make_csv_fr.py
"""

import csv
import json
import os
import re

from bs4 import BeautifulSoup

HTML_DIR = "html_fr"
OCCUPATIONS_FILE = "occupations_fr.json"
OUTPUT_FILE = "occupations_fr.csv"
SALAIRES_FILE = "salaires_fr.csv"  # Optionnel : données DARES/INSEE

# Durée légale annuelle en France
HEURES_ANNUELLES = 1607

# Mapping niveaux de formation ROME → niveaux normalisés
NIVEAUX_EDUCATION = {
    "cap": "CAP/BEP",
    "bep": "CAP/BEP",
    "bac": "Bac",
    "bac pro": "Bac",
    "bac+2": "Bac+2 (BTS/DUT)",
    "bts": "Bac+2 (BTS/DUT)",
    "dut": "Bac+2 (BTS/DUT)",
    "licence": "Bac+3 (Licence)",
    "bac+3": "Bac+3 (Licence)",
    "master": "Bac+5 (Master/Ingénieur)",
    "bac+5": "Bac+5 (Master/Ingénieur)",
    "ingénieur": "Bac+5 (Master/Ingénieur)",
    "doctorat": "Bac+8 (Doctorat)",
    "bac+8": "Bac+8 (Doctorat)",
}


def normalize_education(raw_text):
    """Normalise un texte de niveau d'éducation vers les niveaux français standards."""
    if not raw_text:
        return ""
    text = raw_text.lower().strip()
    for key, value in NIVEAUX_EDUCATION.items():
        if key in text:
            return value
    return raw_text.strip()


def extract_from_json(json_path, occ_meta):
    """Extraire les données d'une fiche ROME au format JSON (mode API)."""
    with open(json_path) as f:
        data = json.load(f)

    row = {
        "title": occ_meta["title"],
        "category": occ_meta["category"],
        "slug": occ_meta["slug"],
        "code_rome": occ_meta["code_rome"],
        "url": occ_meta["url"],
        "niveau_education": "",
        "salaire_median_annuel": "",
        "salaire_median_horaire": "",
        "nombre_emplois": "",
        "perspectives": "",
        "perspectives_desc": "",
        "description": "",
    }

    # Extraire la description si disponible
    if isinstance(data, dict):
        row["description"] = data.get("definition", "")

        # Niveau d'accès (si présent dans l'API)
        acces = data.get("acces", "")
        if acces:
            row["niveau_education"] = normalize_education(acces)

    return row


def extract_from_html(html_path, occ_meta):
    """Extraire les données d'une fiche ROME au format HTML (mode scraping)."""
    with open(html_path) as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    row = {
        "title": occ_meta["title"],
        "category": occ_meta["category"],
        "slug": occ_meta["slug"],
        "code_rome": occ_meta["code_rome"],
        "url": occ_meta["url"],
        "niveau_education": "",
        "salaire_median_annuel": "",
        "salaire_median_horaire": "",
        "nombre_emplois": "",
        "perspectives": "",
        "perspectives_desc": "",
        "description": "",
    }

    # Extraire la description du métier
    desc_el = soup.find("div", class_="description") or soup.find("section", class_="description")
    if desc_el:
        row["description"] = re.sub(r'\s+', ' ', desc_el.get_text()).strip()

    # Chercher le niveau d'accès
    for el in soup.find_all(["dt", "th", "h3", "strong"]):
        text = el.get_text().lower()
        if "accès" in text or "formation" in text or "diplôme" in text:
            sibling = el.find_next(["dd", "td", "p", "span"])
            if sibling:
                row["niveau_education"] = normalize_education(sibling.get_text())
                break

    return row


def load_salaires():
    """Charger les données salariales DARES/INSEE si disponibles."""
    if not os.path.exists(SALAIRES_FILE):
        return {}
    salaires = {}
    with open(SALAIRES_FILE) as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("code_rome", "").strip()
            if code:
                salaires[code] = {
                    "salaire_median_annuel": row.get("salaire_median_annuel", ""),
                    "nombre_emplois": row.get("nombre_emplois", ""),
                    "perspectives": row.get("perspectives", ""),
                    "perspectives_desc": row.get("perspectives_desc", ""),
                }
    return salaires


def main():
    with open(OCCUPATIONS_FILE) as f:
        occupations = json.load(f)

    salaires = load_salaires()

    fieldnames = [
        "title", "category", "slug", "code_rome",
        "salaire_median_annuel", "salaire_median_horaire",
        "niveau_education",
        "nombre_emplois", "perspectives", "perspectives_desc",
        "description", "url",
    ]

    rows = []
    missing = 0
    for occ in occupations:
        json_path = os.path.join(HTML_DIR, f"{occ['slug']}.json")
        html_path = os.path.join(HTML_DIR, f"{occ['slug']}.html")

        if os.path.exists(json_path):
            row = extract_from_json(json_path, occ)
        elif os.path.exists(html_path):
            row = extract_from_html(html_path, occ)
        else:
            missing += 1
            continue

        # Enrichir avec données salariales DARES/INSEE
        code = occ["code_rome"]
        if code in salaires:
            for key in ["salaire_median_annuel", "nombre_emplois",
                        "perspectives", "perspectives_desc"]:
                if salaires[code].get(key) and not row.get(key):
                    row[key] = salaires[code][key]

        # Calculer le salaire horaire si on a l'annuel
        if row["salaire_median_annuel"] and not row["salaire_median_horaire"]:
            try:
                annuel = float(row["salaire_median_annuel"])
                row["salaire_median_horaire"] = f"{annuel / HEURES_ANNUELLES:.2f}"
            except ValueError:
                pass

        rows.append(row)

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Écrit {len(rows)} lignes dans {OUTPUT_FILE} (fichiers manquants : {missing})")

    if rows:
        print(f"\nExemples :")
        for r in rows[:3]:
            sal = r['salaire_median_annuel'] or '?'
            emp = r['nombre_emplois'] or '?'
            print(f"  {r['title']} ({r['code_rome']}): {sal}€/an, {emp} emplois")


if __name__ == "__main__":
    main()
