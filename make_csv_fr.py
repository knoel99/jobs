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
    Plusieurs FAP (familles professionnelles) peuvent être retournées
    pour un même code ROME → on fait la moyenne pondérée des SAL3.
    """
    salaires = data.get("salaires")
    if not salaires:
        return "", ""

    periodes = salaires.get("valeursParPeriode", [])
    if not periodes:
        return "", ""

    # Collecter SAL3 (ou SAL1 en fallback) de chaque FAP
    sal_values = []
    for periode in periodes:
        montants = periode.get("salaireValeurMontant", [])
        sal3 = None
        sal1 = None
        for m in montants:
            code = m.get("codeNomenclature", "")
            montant = m.get("valeurPrincipaleMontant")
            if code == "SAL3" and montant:
                sal3 = montant
            elif code == "SAL1" and montant:
                sal1 = montant
        val = sal3 or sal1
        if val:
            sal_values.append(val)

    if sal_values:
        sal_moyen = sum(sal_values) / len(sal_values)
        annuel = round(sal_moyen * 12)
        horaire = f"{sal_moyen * 12 / HEURES_ANNUELLES:.2f}"
        return str(annuel), horaire

    return "", ""


def extract_demandeurs(data):
    """Extraire le nombre de demandeurs d'emploi catégorie ABC.

    Les périodes contiennent des lignes pour chaque catégorie (A, B, C, ABC,
    ABCDE, ABCDEFG, D, E, F, G). Ces catégories sont imbriquées :
    ABC = A+B+C, ABCDE = ABC+D+E, etc.
    On prend uniquement la ligne ABC (catégories A+B+C = chiffre officiel DEFM).
    """
    demandeurs = data.get("demandeurs")
    if not demandeurs:
        return ""

    periodes = demandeurs.get("listeValeursParPeriode", [])
    if not periodes:
        return ""

    # Prendre la ligne ABC (demandeurs cat. A+B+C)
    for p in periodes:
        if p.get("codeNomenclature") == "ABC":
            nb = p.get("valeurPrincipaleNombre")
            if nb:
                return str(nb)

    # Fallback: catégorie A seule
    for p in periodes:
        if p.get("codeNomenclature") == "A":
            nb = p.get("valeurPrincipaleNombre")
            if nb:
                return str(nb)

    return ""


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
    """Extraire l'indicateur principal de tension (perspectives employeur).

    Structure: tensions.listeValeursParPeriode[*]
    Codes nomenclature :
      - PERSPECTIVE : indicateur principal (score décimal + rang 1-5)
      - INT_EMB : intensité d'embauche
      - MAIN_OEUVRE : manque de main d'œuvre
      - ATTR_SALARIALE, COND_TRAVAIL, DUR_EMPL, etc.

    valeurPrincipaleNombre = rang 1 à 5 (1=très défavorable, 5=très favorable)
    """
    tensions = data.get("tensions")
    if not tensions:
        return "", ""

    periodes = tensions.get("listeValeursParPeriode", [])
    if not periodes:
        return "", ""

    # Chercher l'indicateur principal PERSPECTIVE
    for p in periodes:
        code_nom = p.get("codeNomenclature", "")
        if code_nom == "PERSPECTIVE":
            rang = p.get("valeurPrincipaleNombre")
            if rang is not None:
                # Rang 1-5 → description
                descs = {
                    1: "Très défavorable",
                    2: "Défavorable",
                    3: "Neutre",
                    4: "Favorable",
                    5: "Très favorable",
                }
                return str(rang), descs.get(rang, "")
            break

    # Fallback: chercher INT_EMB (intensité d'embauche)
    for p in periodes:
        code_nom = p.get("codeNomenclature", "")
        if code_nom == "INT_EMB":
            rang = p.get("valeurPrincipaleNombre")
            if rang is not None:
                return str(rang), "Intensité embauche"

    return "", ""


def extract_niveau_education(data):
    """Extraire le niveau d'éducation requis depuis metier.accesEmploi.

    Cherche le niveau le plus élevé mentionné dans le texte d'accès à l'emploi.
    Retourne une valeur normalisée compatible avec le frontend.
    """
    metier = data.get("metier", {})
    if not isinstance(metier, dict):
        return ""

    acces = metier.get("accesEmploi", "")
    if not acces:
        return ""

    text = acces.lower()

    # Du plus élevé au plus bas — on prend le plus haut mentionné
    if "bac+8" in text or "bac + 8" in text or "doctorat" in text or "docteur" in text:
        return "Bac+8 (Doctorat)"
    if "bac+5" in text or "bac + 5" in text or "master" in text or "ingénieur" in text:
        return "Bac+5 (Master/Ingénieur)"
    if "bac+3" in text or "bac + 3" in text or "licence" in text:
        return "Bac+3 (Licence)"
    if "bac+2" in text or "bac + 2" in text or "bts" in text or "dut" in text or "deust" in text:
        return "Bac+2 (BTS/DUT)"
    if "bac pro" in text or "bac " in text or "baccalauréat" in text or "niveau bac" in text:
        return "Bac"
    if "cap" in text or "bep" in text or "niveau 3" in text:
        return "CAP/BEP"
    if "sans diplôme" in text or "sans qualification" in text:
        return "CAP/BEP"

    return ""


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
        "niveau_education": extract_niveau_education(data),
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
            tdesc = r['tension_desc'] or ''
            print(f"  {r['title']} ({r['code_rome']}): {sal}€/an, {dem} DE, {off} offres, tension={ten}/5 {tdesc}")


if __name__ == "__main__":
    main()
