"""
Construit un CSV des métiers français à partir des fiches ROME scrapées.

Lit les fichiers html_fr/<slug>.json (API France Travail), écrit occupations_fr.csv.

Extrait :
  - Description du métier (depuis metier.definition)
  - Salaire moyen mensuel net (depuis salaires → SAL3 moyen × 12)
  - Nombre de demandeurs d'emploi (depuis demandeurs)
  - Nombre d'offres (depuis offres)
  - Tensions recrutement (depuis tensions)

Usage:
    uv run python make_csv_fr.py
"""

import csv
import json
import os

HTML_DIR = "html_fr"
OCCUPATIONS_FILE = "occupations_fr.json"
OUTPUT_FILE = "occupations_fr.csv"

# Durée légale annuelle en France
HEURES_ANNUELLES = 1607


def extract_salary(data):
    """Extraire le salaire moyen annuel depuis les données salaires API.

    Structure: data["salaires"]["valeursParPeriode"][*]["salaireValeurMontant"]
    SAL1 = débutant, SAL2 = expérimenté, SAL3 = moyen
    Les montants sont en net mensuel.
    """
    salaires = data.get("salaires")
    if not salaires:
        return "", ""

    periodes = salaires.get("valeursParPeriode", [])
    if not periodes:
        return "", ""

    # Prendre la période la plus récente
    periode = periodes[-1]
    montants = periode.get("salaireValeurMontant", [])

    sal_moyen = None
    for m in montants:
        code = m.get("codeNomenclature", "")
        montant = m.get("valeurPrincipaleMontant")
        if code == "SAL3" and montant:  # SAL3 = salaire moyen
            sal_moyen = montant
        elif code == "SAL1" and montant and sal_moyen is None:
            sal_moyen = montant  # Fallback sur SAL1 si pas de SAL3

    if sal_moyen:
        annuel = round(sal_moyen * 12)
        horaire = f"{sal_moyen * 12 / HEURES_ANNUELLES:.2f}"
        return str(annuel), horaire

    return "", ""


def extract_demandeurs(data):
    """Extraire le nombre total de demandeurs d'emploi (catégorie A+B+C)."""
    demandeurs = data.get("demandeurs")
    if not demandeurs:
        return ""

    periodes = demandeurs.get("listeValeursParPeriode", [])
    if not periodes:
        return ""

    # Sommer toutes les catégories pour le dernier trimestre
    total = 0
    for p in periodes:
        nb = p.get("valeurPrincipaleNombre")
        if nb:
            total += nb

    return str(total) if total > 0 else ""


def extract_offres(data):
    """Extraire le nombre total d'offres d'emploi."""
    offres = data.get("offres")
    if not offres:
        return ""

    periodes = offres.get("listeValeursParPeriode", [])
    if not periodes:
        return ""

    total = 0
    for p in periodes:
        nb = p.get("valeurPrincipaleNombre")
        if nb:
            total += nb

    return str(total) if total > 0 else ""


def extract_tensions(data):
    """Extraire l'indicateur de tension (difficulté de recrutement)."""
    tensions = data.get("tensions")
    if not tensions:
        return "", ""

    periodes = tensions.get("listeValeursParPeriode", [])
    if not periodes:
        return "", ""

    # Chercher l'indicateur global de tension (INDIC_TENSION)
    for p in periodes:
        code_nom = p.get("codeNomenclature", "")
        if code_nom == "INDIC_TENSION":
            val = p.get("valeurPrincipaleDecimale") or p.get("valeurPrincipaleRang")
            if val is not None:
                # Tension de 0 à 1 → convertir en description
                if isinstance(val, float):
                    if val >= 0.7:
                        desc = "Forte tension"
                    elif val >= 0.4:
                        desc = "Tension modérée"
                    else:
                        desc = "Faible tension"
                    return str(round(val * 100)), desc
                return str(val), ""

    # Fallback: prendre la première valeur disponible
    p = periodes[0]
    val = p.get("valeurPrincipaleDecimale") or p.get("valeurPrincipaleRang")
    lib = p.get("libNomenclature", "")
    if val is not None:
        return str(round(val * 100) if isinstance(val, float) else val), lib

    return "", ""


def extract_description(data):
    """Extraire la description du métier."""
    metier = data.get("metier", {})
    if isinstance(metier, dict):
        return metier.get("definition", "")
    return ""


def extract_from_json(json_path, occ_meta):
    """Extraire toutes les données d'un fichier JSON scrapé."""
    with open(json_path) as f:
        data = json.load(f)

    sal_annuel, sal_horaire = extract_salary(data)
    demandeurs = extract_demandeurs(data)
    offres = extract_offres(data)
    tension_pct, tension_desc = extract_tensions(data)
    description = extract_description(data)

    return {
        "title": occ_meta["title"],
        "category": occ_meta["category"],
        "slug": occ_meta["slug"],
        "code_rome": occ_meta["code_rome"],
        "url": occ_meta["url"],
        "salaire_median_annuel": sal_annuel,
        "salaire_median_horaire": sal_horaire,
        "niveau_education": "",
        "nombre_demandeurs": demandeurs,
        "nombre_offres": offres,
        "tension_pct": tension_pct,
        "tension_desc": tension_desc,
        "description": description,
    }


def main():
    with open(OCCUPATIONS_FILE) as f:
        occupations = json.load(f)

    fieldnames = [
        "title", "category", "slug", "code_rome",
        "salaire_median_annuel", "salaire_median_horaire",
        "niveau_education",
        "nombre_demandeurs", "nombre_offres",
        "tension_pct", "tension_desc",
        "description", "url",
    ]

    rows = []
    missing = 0
    for occ in occupations:
        json_path = os.path.join(HTML_DIR, f"{occ['slug']}.json")

        if os.path.exists(json_path):
            row = extract_from_json(json_path, occ)
        else:
            missing += 1
            continue

        rows.append(row)

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Écrit {len(rows)} lignes dans {OUTPUT_FILE} (fichiers manquants : {missing})")

    # Stats
    with_salary = sum(1 for r in rows if r["salaire_median_annuel"])
    with_demandeurs = sum(1 for r in rows if r["nombre_demandeurs"])
    with_offres = sum(1 for r in rows if r["nombre_offres"])
    with_tension = sum(1 for r in rows if r["tension_pct"])

    print(f"\nCouverture :")
    print(f"  Salaires : {with_salary}/{len(rows)}")
    print(f"  Demandeurs : {with_demandeurs}/{len(rows)}")
    print(f"  Offres : {with_offres}/{len(rows)}")
    print(f"  Tensions : {with_tension}/{len(rows)}")

    if rows:
        print(f"\nExemples :")
        for r in rows[:5]:
            sal = r['salaire_median_annuel'] or '?'
            dem = r['nombre_demandeurs'] or '?'
            off = r['nombre_offres'] or '?'
            ten = r['tension_pct'] or '?'
            print(f"  {r['title']} ({r['code_rome']}): {sal}€/an, {dem} DE, {off} offres, tension={ten}%")


if __name__ == "__main__":
    main()
