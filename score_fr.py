"""
Score l'exposition à l'IA de chaque métier français via un LLM (OpenRouter).

Lit les descriptions depuis html_fr/ (JSON ou pages_fr/), envoie chaque fiche
au LLM avec un prompt adapté au contexte français, collecte les scores.

Les résultats sont sauvegardés incrémentalement dans scores_fr.json.

Usage:
    uv run python score_fr.py
    uv run python score_fr.py --model google/gemini-3-flash-preview
    uv run python score_fr.py --start 0 --end 10
"""

import argparse
import json
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "google/gemini-3-flash-preview"
OUTPUT_FILE = "scores_fr.json"
API_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """\
Tu es un analyste expert évaluant l'exposition des métiers à l'intelligence \
artificielle. Tu vas recevoir la description d'un métier issu du répertoire \
ROME (Répertoire Opérationnel des Métiers et des Emplois) français.

Évalue l'**exposition globale à l'IA** de ce métier sur une échelle de 0 à 10.

L'exposition à l'IA mesure : dans quelle mesure l'IA va-t-elle transformer \
ce métier ? Considère à la fois les effets directs (l'IA automatise des \
tâches actuellement effectuées par des humains) et les effets indirects \
(l'IA rend chaque travailleur si productif que moins de postes sont \
nécessaires).

Un signal clé est la nature numérique du travail. Si le métier peut être \
exercé entièrement depuis un bureau sur un ordinateur — rédaction, \
programmation, analyse, communication — alors l'exposition à l'IA est \
intrinsèquement élevée (7+), car les capacités de l'IA dans les domaines \
numériques progressent rapidement. À l'inverse, les métiers nécessitant une \
présence physique, une habileté manuelle ou une interaction humaine en temps \
réel dans le monde physique ont une barrière naturelle à l'exposition IA.

Note : le droit du travail français offre une protection de l'emploi plus \
forte (CDI, conventions collectives, CSE), ce qui peut ralentir l'impact \
organisationnel de l'IA sans changer l'exposition technique du métier. \
Évalue l'exposition TECHNIQUE, pas la vitesse d'adoption.

Utilise ces repères pour calibrer ton score :

- **0–1 : Exposition minimale.** Le travail est presque entièrement \
physique, manuel, ou nécessite une présence humaine en temps réel dans des \
environnements imprévisibles. L'IA n'a essentiellement aucun impact. \
Exemples : couvreur, paysagiste, maçon, éboueur.

- **2–3 : Exposition faible.** Travail principalement physique ou \
relationnel. L'IA peut aider sur des tâches périphériques (planification, \
paperasse) mais ne touche pas le cœur du métier. \
Exemples : électricien, plombier, pompier, aide-soignant.

- **4–5 : Exposition modérée.** Mix de travail physique/relationnel et de \
travail intellectuel. L'IA peut significativement aider sur les aspects \
traitement de l'information, mais une part importante du métier nécessite \
encore une présence humaine. \
Exemples : infirmier, policier, vétérinaire, éducateur spécialisé.

- **6–7 : Exposition élevée.** Travail principalement intellectuel avec \
un certain besoin de jugement humain, relations ou présence physique. Les \
outils IA sont déjà utiles et les travailleurs utilisant l'IA sont \
nettement plus productifs. \
Exemples : enseignant, manager, comptable, journaliste, avocat.

- **8–9 : Exposition très élevée.** Le métier s'exerce presque \
entièrement sur ordinateur. Toutes les tâches principales — rédaction, \
codage, analyse, conception, communication — sont dans des domaines où \
l'IA progresse rapidement. Le métier fait face à une restructuration \
majeure. \
Exemples : développeur informatique, graphiste, traducteur, analyste de \
données, assistant juridique, rédacteur.

- **10 : Exposition maximale.** Traitement d'information routinier, \
entièrement numérique, sans composante physique. L'IA peut déjà faire \
la majorité du travail aujourd'hui. \
Exemples : opérateur de saisie, télévendeur, agent de téléconseil.

Réponds UNIQUEMENT avec un objet JSON dans ce format exact, sans autre texte :
{
  "exposure": <0-10>,
  "rationale": "<2-3 phrases expliquant les facteurs clés, en français>"
}\
"""


def get_description(slug):
    """Récupérer la description d'un métier (JSON API ou Markdown)."""
    # Essayer d'abord le JSON (mode API)
    json_path = os.path.join("html_fr", f"{slug}.json")
    if os.path.exists(json_path):
        with open(json_path) as f:
            data = json.load(f)
        if isinstance(data, dict):
            parts = []
            metier = data.get("metier", {})
            if isinstance(metier, dict):
                if metier.get("definition"):
                    parts.append(f"Définition : {metier['definition']}")
                if metier.get("accesEmploi"):
                    parts.append(f"Accès au métier : {metier['accesEmploi']}")
                comps = metier.get("competencesMobilisees", [])
                if comps:
                    parts.append("Compétences : " + ", ".join(
                        c.get("libelle", str(c)) for c in comps if isinstance(c, dict)))
                ctx = metier.get("contextesTravail", [])
                if ctx:
                    parts.append("Contexte de travail : " + ", ".join(
                        c.get("libelle", str(c)) for c in ctx if isinstance(c, dict)))
                if metier.get("emploiCadre") is not None:
                    parts.append(f"Emploi cadre : {'Oui' if metier['emploiCadre'] else 'Non'}")
                if metier.get("transitionNumerique") is not None:
                    parts.append(f"Transition numérique : {'Oui' if metier['transitionNumerique'] else 'Non'}")
            # Fallback: données brutes si pas de clé metier
            return "\n\n".join(parts) if parts else json.dumps(data, ensure_ascii=False)[:5000]
        return json.dumps(data, ensure_ascii=False)[:5000]

    # Sinon essayer le Markdown
    md_path = os.path.join("pages_fr", f"{slug}.md")
    if os.path.exists(md_path):
        with open(md_path) as f:
            return f.read()

    # En dernier recours, HTML
    html_path = os.path.join("html_fr", f"{slug}.html")
    if os.path.exists(html_path):
        from bs4 import BeautifulSoup
        with open(html_path) as f:
            soup = BeautifulSoup(f.read(), "html.parser")
        return soup.get_text(separator="\n", strip=True)[:5000]

    return None


def score_occupation(client, text, title, code_rome, model, max_retries=4):
    """Envoyer un métier au LLM et parser la réponse structurée."""
    user_msg = f"Métier : {title} (Code ROME : {code_rome})\n\n{text}"

    for attempt in range(max_retries + 1):
        try:
            response = client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_msg},
                    ],
                    "temperature": 0.2,
                },
                timeout=60,
            )
            if response.status_code in (429, 403, 502, 503):
                wait = 2 ** (attempt + 1)
                print(f"{response.status_code}, retry dans {wait}s...", end=" ", flush=True)
                time.sleep(wait)
                continue
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]

            # Nettoyer les code fences markdown
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            return json.loads(content)
        except httpx.HTTPError:
            if attempt < max_retries:
                wait = 2 ** (attempt + 1)
                print(f"erreur réseau, retry dans {wait}s...", end=" ", flush=True)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Échec après {max_retries} retries")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=None)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--force", action="store_true",
                        help="Re-scorer même si déjà en cache")
    args = parser.parse_args()

    with open("occupations_fr.json") as f:
        occupations = json.load(f)

    subset = occupations[args.start:args.end]

    # Charger scores existants
    scores = {}
    if os.path.exists(OUTPUT_FILE) and not args.force:
        with open(OUTPUT_FILE) as f:
            for entry in json.load(f):
                scores[entry["slug"]] = entry

    print(f"Scoring {len(subset)} métiers avec {args.model}")
    print(f"Déjà en cache : {len(scores)}")

    errors = []
    client = httpx.Client()

    for i, occ in enumerate(subset):
        slug = occ["slug"]

        if slug in scores:
            continue

        text = get_description(slug)
        if not text:
            print(f"  [{i+1}] PASSE {slug} (pas de données)")
            continue

        print(f"  [{i+1}/{len(subset)}] {occ['title']}...", end=" ", flush=True)

        try:
            result = score_occupation(
                client, text, occ["title"], occ["code_rome"], args.model
            )
            scores[slug] = {
                "slug": slug,
                "title": occ["title"],
                "code_rome": occ["code_rome"],
                **result,
            }
            print(f"exposition={result['exposure']}")
        except Exception as e:
            print(f"ERREUR: {e}")
            errors.append(slug)

        # Sauvegarder après chaque score (checkpoint incrémental)
        with open(OUTPUT_FILE, "w") as f:
            json.dump(list(scores.values()), f, ensure_ascii=False, indent=2)

        if i < len(subset) - 1:
            time.sleep(args.delay)

    client.close()

    print(f"\nTerminé. {len(scores)} métiers scorés, {len(errors)} erreurs.")
    if errors:
        print(f"Erreurs : {errors}")

    # Stats résumé
    vals = [s for s in scores.values() if "exposure" in s]
    if vals:
        avg = sum(s["exposure"] for s in vals) / len(vals)
        by_score = {}
        for s in vals:
            bucket = s["exposure"]
            by_score[bucket] = by_score.get(bucket, 0) + 1
        print(f"\nExposition moyenne sur {len(vals)} métiers : {avg:.1f}")
        print("Distribution :")
        for k in sorted(by_score):
            print(f"  {k}: {'█' * by_score[k]} ({by_score[k]})")


if __name__ == "__main__":
    main()
