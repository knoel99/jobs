# CLAUDE.md — AI Exposure of the Job Market

## Projet

Analyse de l'exposition des métiers à l'IA, initialement basé sur les données du Bureau of Labor Statistics (BLS) américain. Pipeline de données : scraping → parsing → scoring IA → visualisation interactive (treemap).

## Stack technique

- **Python 3.10** avec gestionnaire de paquets `uv`
- **Playwright** pour le scraping (mode non-headless, les sites bloquent les bots)
- **BeautifulSoup** pour le parsing HTML
- **httpx** pour les appels API (OpenRouter / Gemini Flash)
- **Frontend** : HTML/CSS/JS vanilla, rendu canvas (pas de framework)

## Commandes essentielles

```bash
uv sync                          # Installer les dépendances
uv run python scrape.py          # Scraper les pages (nécessite Playwright)
uv run python process.py         # HTML → Markdown
uv run python make_csv.py        # Extraire stats → occupations.csv
uv run python score.py           # Scorer exposition IA via LLM
uv run python build_site_data.py # Fusionner → site/data.json
uv run python make_prompt.py     # Générer prompt.md (pour analyse LLM)
```

## Pipeline de données

1. `scrape.py` → télécharge le HTML brut dans `html/`
2. `process.py` / `parse_detail.py` → convertit en Markdown dans `pages/`
3. `make_csv.py` → extrait les stats structurées → `occupations.csv`
4. `score.py` → score d'exposition IA (0-10) via LLM → `scores.json`
5. `build_site_data.py` → fusionne CSV + scores → `site/data.json`
6. `site/index.html` → visualisation interactive (treemap)

## Fichiers clés

| Fichier | Rôle |
|---|---|
| `occupations.json` | Liste maître des 342 métiers (titre, URL, catégorie, slug) |
| `occupations.csv` | Stats extraites (salaire, éducation, emploi, perspectives) |
| `scores.json` | Scores d'exposition IA avec justifications |
| `site/data.json` | Données compactes pour le frontend |
| `site/index.html` | Visualisation interactive |

## Variables d'environnement

- `OPENROUTER_API_KEY` — requis dans `.env` pour le scoring LLM

## Conventions

- Les slugs servent d'identifiants uniques entre tous les fichiers
- Le cache HTML empêche de re-télécharger les pages existantes
- `scores.json` supporte la reprise incrémentale (checkpoint après chaque score)
- Le scoring utilise temperature=0.2 pour la reproductibilité

---

## Adaptation pour la France — Plan de travail

### Source de données : France Travail (ex-Pôle Emploi) + DARES + INSEE

Le BLS américain n'a pas d'équivalent exact en France, mais on peut reconstituer des données comparables :

| Donnée US (BLS) | Équivalent France | Source |
|---|---|---|
| Liste des métiers (342 occupations) | **ROME** (Répertoire Opérationnel des Métiers et des Emplois) ~530 fiches | France Travail |
| Salaire médian | Salaire médian par PCS/ROME | **DARES** / **INSEE** (DADS) |
| Nombre d'emplois | Emploi par métier | **DARES** (Portraits statistiques des métiers) |
| Perspectives d'emploi (outlook) | Projections PMQ (Prospective des Métiers et Qualifications) | **France Stratégie / DARES** |
| Niveau d'éducation requis | Niveau de formation (CAP, Bac, Bac+2, etc.) | Fiches ROME |
| Code SOC | Code ROME (ex: M1805 pour développeur) | France Travail |

### Modifications par script

#### 1. `occupations.json` → `occupations_fr.json`
- Remplacer par la liste des fiches ROME
- Format : `{"title": "Développement informatique", "slug": "developpement-informatique", "code_rome": "M1805", "url": "https://candidat.francetravail.fr/marche-du-travail/fichemetierrome?codeRome=M1805"}`
- Source : API France Travail (anciennement API Emploi Store)

#### 2. `scrape.py` → `scrape_fr.py`
- Scraper les fiches ROME depuis France Travail
- Alternative : utiliser l'**API REST France Travail** (plus fiable que le scraping)
  - Endpoint : `https://api.francetravail.io/partenaire/rome/v1/metier`
  - Authentification OAuth2 requise
- Stocker dans `html_fr/` ou `data_fr/`

#### 3. `make_csv.py` → `make_csv_fr.py`
- Parser le format des fiches ROME (structure HTML différente)
- Salaires en **EUR** (pas USD), conversion heures : 1607h/an (durée légale France)
- Niveaux d'éducation français : CAP/BEP, Bac, Bac+2 (BTS/DUT), Bac+3 (Licence), Bac+5 (Master), Bac+8 (Doctorat)
- Pas de projection 10 ans directe → utiliser les données PMQ de France Stratégie

#### 4. `score.py` → adapter le SYSTEM_PROMPT
- Changer la référence au BLS par les fiches ROME
- Adapter les exemples de calibration aux métiers français
- Ajouter le contexte réglementaire français (Code du travail, protection de l'emploi plus forte)
- Le scoring 0-10 reste pertinent tel quel

#### 5. `build_site_data.py` — changements mineurs
- Adapter les noms de champs (`median_pay_annual` → `salaire_median_annuel`)
- Ajouter le code ROME

#### 6. `site/index.html` — localisation
- Traduire l'interface en français
- Afficher les salaires en EUR (€)
- Adapter les catégories de métiers aux familles ROME
- Adapter les niveaux d'éducation au système français

### Priorité d'implémentation

1. **Obtenir les données ROME** via l'API France Travail (créer un compte développeur)
2. **Croiser avec les données salariales** DARES/INSEE
3. **Adapter le scoring** (prompt + calibration)
4. **Adapter le frontend** (traduction + EUR)
5. **Générer la visualisation** pour ~530 métiers français
