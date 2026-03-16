"""
Construit un JSON compact pour le site web français en fusionnant
le CSV des stats et les scores d'exposition IA.

Lit occupations_fr.csv (stats) et scores_fr.json (exposition IA).
Écrit site_fr/data.json.

Usage:
    uv run python build_site_data_fr.py
"""

import csv
import json
import os


def main():
    # Charger les scores d'exposition IA
    scores = {}
    if os.path.exists("scores_fr.json"):
        with open("scores_fr.json") as f:
            scores_list = json.load(f)
        scores = {s["slug"]: s for s in scores_list}

    # Charger le CSV des stats
    rows = []
    if os.path.exists("occupations_fr.csv"):
        with open("occupations_fr.csv") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    else:
        # Fallback : construire depuis occupations_fr.json + scores
        with open("occupations_fr.json") as f:
            occupations = json.load(f)
        for occ in occupations:
            rows.append({
                "title": occ["title"],
                "slug": occ["slug"],
                "category": occ["category"],
                "code_rome": occ["code_rome"],
                "salaire_median_annuel": "",
                "nombre_demandeurs": "",
                "nombre_offres": "",
                "tension_pct": "",
                "tension_desc": "",
                "niveau_education": "",
                "url": occ["url"],
            })

    # Fusionner
    data = []
    for row in rows:
        slug = row["slug"]
        score = scores.get(slug, {})

        salaire = row.get("salaire_median_annuel", "")
        demandeurs = row.get("nombre_demandeurs", "")
        offres = row.get("nombre_offres", "")
        tension = row.get("tension_pct", "")

        data.append({
            "title": row["title"],
            "slug": slug,
            "category": row["category"],
            "code_rome": row.get("code_rome", ""),
            "pay": int(salaire) if salaire else None,
            "demandeurs": int(demandeurs) if demandeurs else None,
            "offres": int(offres) if offres else None,
            "tension": int(tension) if tension else None,
            "tension_desc": row.get("tension_desc", ""),
            "education": row.get("niveau_education", ""),
            "exposure": score.get("exposure"),
            "exposure_rationale": score.get("rationale"),
            "description": row.get("description", ""),
            "url": row.get("url", ""),
        })

    os.makedirs("site_fr", exist_ok=True)
    with open("site_fr/data.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"Écrit {len(data)} métiers dans site_fr/data.json")
    with_pay = sum(1 for d in data if d["pay"])
    with_demandeurs = sum(1 for d in data if d["demandeurs"])
    with_offres = sum(1 for d in data if d["offres"])
    with_tension = sum(1 for d in data if d["tension"])
    scored = sum(1 for d in data if d["exposure"] is not None)
    print(f"Salaires : {with_pay}/{len(data)}")
    print(f"Demandeurs : {with_demandeurs}/{len(data)}")
    print(f"Offres : {with_offres}/{len(data)}")
    print(f"Tensions : {with_tension}/{len(data)}")
    print(f"Métiers scorés : {scored}/{len(data)}")


if __name__ == "__main__":
    main()
