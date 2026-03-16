# Mémo : Exposition des métiers français à l'intelligence artificielle

**Date** : Mars 2026
**Source des données** : France Travail (fiches ROME), DARES, API marché du travail
**Scoring IA** : Gemini Flash via OpenRouter (temperature=0.2)
**Périmètre** : 61 métiers représentatifs du marché de l'emploi français

---

## Introduction

### Pourquoi cette application ?

L'intelligence artificielle générative progresse à un rythme sans précédent. En quelques années, les modèles de langage sont passés de curiosités de laboratoire à des outils capables de rédiger, coder, analyser, traduire et créer du contenu visuel à un niveau professionnel. Cette accélération pose une question concrète et urgente pour le marché du travail : **quels métiers seront les plus transformés par l'IA, et dans quelle mesure ?**

Le débat public oscille entre deux extrêmes — un techno-optimisme qui minimise les disruptions, et un catastrophisme qui prédit la fin du travail. Il manque un outil factuel, ancré dans les données réelles de l'emploi, permettant à chacun — décideurs publics, dirigeants d'entreprise, salariés, étudiants — de visualiser concrètement l'exposition de chaque métier à l'IA.

Ce projet s'inspire du travail d'Andrej Karpathy sur les données du Bureau of Labor Statistics américain, et l'adapte au contexte français en s'appuyant sur le **Répertoire Opérationnel des Métiers et des Emplois (ROME)** de France Travail et les données statistiques du marché du travail français (DARES, INSEE).

### Comment ça fonctionne ?

L'application repose sur un **pipeline de données en 5 étapes** :

1. **Collecte des données métiers** — Les fiches ROME et les statistiques du marché du travail (salaires, demandeurs d'emploi, offres, tensions de recrutement) sont récupérées via l'API REST de France Travail (authentification OAuth2). Les données brutes sont stockées localement en JSON pour permettre un traitement reproductible.

2. **Structuration** — Un script Python (`make_csv_fr.py`) parse les données JSON de l'API et extrait pour chaque métier : le salaire médian annuel net (calculé à partir des salaires mensuels moyens par famille professionnelle), le nombre de demandeurs d'emploi (catégories A+B+C), le nombre d'offres, et l'indicateur de tension du marché (rang 1 à 5, de « Très défavorable » à « Très favorable »).

3. **Scoring par IA** — Chaque fiche métier (description, compétences, conditions d'accès) est envoyée à un modèle de langage (Gemini Flash, via OpenRouter) avec un prompt expert calibré. Le modèle évalue l'exposition technique du métier à l'IA sur une échelle de 0 (aucun impact) à 10 (automatisation quasi-totale), en justifiant son score. Le paramètre temperature=0.2 assure la reproductibilité. Le processus est incrémental : les scores sont sauvegardés après chaque évaluation, permettant de reprendre en cas d'interruption.

4. **Fusion des données** — Un script (`build_site_data_fr.py`) fusionne le CSV des statistiques et le fichier des scores IA en un unique `data.json` compact, prêt pour le frontend.

5. **Visualisation interactive** — Une page HTML/CSS/JS vanilla (sans framework) affiche une **treemap** où chaque rectangle représente un métier. La taille du rectangle est proportionnelle au nombre de demandeurs d'emploi (poids économique), et sa couleur encode le score d'exposition IA (gradient vert → orange → rouge). Une vue alternative en colonnes croise l'exposition IA avec l'indicateur de tension du marché. Le survol de chaque métier affiche un tooltip détaillé avec toutes les données et la justification du score IA.

### Choix techniques

- **Python 3.10 + uv** comme gestionnaire de paquets pour un environnement reproductible
- **API REST France Travail** plutôt que scraping HTML, pour la fiabilité et la structure des données
- **Scoring via LLM** plutôt qu'un modèle statistique, car l'évaluation de l'exposition à l'IA nécessite un raisonnement qualitatif sur la nature des tâches de chaque métier
- **Frontend vanilla** (HTML/CSS/JS + Canvas) sans dépendance, pour une visualisation légère et portable
- **Données 100% françaises** : salaires en euros, niveaux d'éducation français (CAP à Doctorat), codes ROME, indicateurs de tension France Travail

---

## Objet

La page web présente une **cartographie interactive** (treemap) de l'exposition de 61 métiers français à l'intelligence artificielle. Chaque métier est représenté par un rectangle dont la **taille** est proportionnelle au nombre de demandeurs d'emploi et la **couleur** reflète le score d'exposition IA (vert = faible, orange/rouge = élevée).

L'utilisateur peut interagir avec la visualisation : survol pour voir le détail d'un métier (salaire, demandeurs, offres, tension, score IA et justification), clic pour accéder à la fiche ROME sur France Travail, et basculement vers une vue « Exposition vs Tension » en colonnes.

---

## Méthodologie

Chaque métier est évalué sur une échelle de **0 à 10** mesurant dans quelle mesure l'IA va transformer le métier, en considérant :

- **Effets directs** : l'IA automatise des tâches actuellement effectuées par des humains
- **Effets indirects** : l'IA rend chaque travailleur si productif que moins de postes sont nécessaires
- **Signal clé** : la nature numérique du travail — un métier exercé entièrement sur ordinateur a une exposition intrinsèquement élevée (7+)

Le scoring évalue l'**exposition technique**, indépendamment des protections du droit du travail français (CDI, conventions collectives, CSE) qui peuvent ralentir l'impact organisationnel sans changer l'exposition fondamentale.

---

## Résultats clés

### Score moyen : 5.7/10

La moyenne d'exposition sur les 61 métiers est de **5.7**, indiquant une exposition globale modérée à élevée du panel étudié.

### Distribution des scores

| Score | Nb métiers | Proportion |
|-------|-----------|------------|
| 1     | 1         | 2%         |
| 2     | 6         | 10%        |
| 3     | 11        | 18%        |
| 4     | 4         | 7%         |
| 5     | 2         | 3%         |
| 6     | 11        | 18%        |
| 7     | 8         | 13%        |
| 8     | 12        | 20%        |
| 9     | 5         | 8%         |
| 10    | 1         | 2%         |

La distribution est **bimodale** : un premier pic autour de 2-3 (métiers manuels/physiques) et un second plus important autour de 7-8 (métiers tertiaires/numériques). Cela reflète la fracture entre économie physique et économie de la connaissance.

### Métiers les plus exposés (8-10)

| Métier | Score | Secteur |
|--------|-------|---------|
| **Téléconseil et télévente** | 10 | Commerce-vente |
| **Développement informatique** | 9 | Informatique-télécoms |
| **Secrétariat** | 9 | Gestion-administration |
| **Conception de contenus multimédias** | 9 | Communication-média |
| **Traduction, interprétariat** | 9 | Communication-média |
| **Études actuarielles en assurances** | 9 | Banque-assurance |
| **Comptabilité** | 8 | Gestion-administration |
| **Contrôle de gestion** | 8 | Gestion-administration |
| **Assistanat de direction** | 8 | Gestion-administration |
| **Expertise et support SI** | 8 | Informatique-télécoms |
| **Administration de SI** | 8 | Informatique-télécoms |
| **Études et développement réseaux télécoms** | 8 | Informatique-télécoms |
| **Conseil et maîtrise d'ouvrage SI** | 8 | Informatique-télécoms |
| **Journalisme et information média** | 8 | Communication-média |
| **Design industriel** | 8 | Arts-spectacles |
| **Droit des affaires** | 8 | Droit-justice |
| **Collaboration juridique** | 8 | Droit-justice |
| **Conseil clientèle en assurances** | 8 | Banque-assurance |

**Profil commun** : métiers exercés principalement sur ordinateur, à forte composante rédactionnelle, analytique ou de traitement d'information.

### Métiers les moins exposés (1-3)

| Métier | Score | Secteur |
|--------|-------|---------|
| **Maçonnerie** | 1 | BTP |
| **Plomberie, chauffage** | 2 | BTP |
| **Peinture en bâtiment** | 2 | BTP |
| **Cuisine** | 2 | Hôtellerie-restauration |
| **Boulangerie - viennoiserie** | 2 | Hôtellerie-restauration |
| **Entretien des espaces verts** | 2 | Agriculture |
| **Nettoyage de locaux** | 2 | Services |
| **Aide-soignant** | 3 | Santé |
| **Kinésithérapie** | 3 | Santé |
| **Électricité bâtiment** | 3 | BTP |
| **Vente en habillement** | 3 | Commerce |
| **Mise en rayon libre-service** | 3 | Commerce |
| **Service en restauration** | 3 | Hôtellerie-restauration |
| **Conduite de transport marchandises** | 3 | Transport |
| **Soudage manuel** | 3 | Industrie |
| **Sécurité et surveillance privées** | 3 | Services |
| **Agriculture et pêche** | 3 | Agriculture |
| **Élevage bovin ou équin** | 3 | Agriculture |

**Profil commun** : métiers requérant une présence physique, une habileté manuelle ou une interaction humaine en temps réel dans le monde réel.

### Analyse par secteur

| Secteur | Métiers | Exposition moyenne |
|---------|---------|-------------------|
| Informatique-télécoms | 6 | **8.0** |
| Communication-média | 4 | **8.3** |
| Gestion-administration | 5 | **8.0** |
| Droit-justice | 2 | **8.0** |
| Banque-assurance | 3 | **8.0** |
| Enseignement-formation | 4 | **6.5** |
| Santé | 6 | **4.3** |
| Commerce-vente | 5 | **5.6** |
| Services-collectivité | 4 | **4.0** |
| Transport-logistique | 3 | **4.3** |
| Industrie | 4 | **4.8** |
| Hôtellerie-restauration | 4 | **3.3** |
| BTP | 5 | **2.6** |
| Arts-spectacles | 3 | **6.7** |
| Agriculture-pêche | 3 | **2.7** |

Les secteurs **tertiaires à dominante numérique** (informatique, communication, gestion, droit, banque-assurance) affichent une exposition moyenne de 8+, tandis que les secteurs **physiques** (BTP, agriculture, hôtellerie) restent sous 3.

---

## Données complémentaires affichées

Au-delà du score IA, la visualisation croise chaque métier avec des données du marché du travail français :

- **Salaire médian annuel** (net, en EUR) — source API France Travail / DARES
- **Nombre de demandeurs d'emploi** (catégories A+B+C) — source France Travail
- **Nombre d'offres d'emploi** — source France Travail
- **Indicateur de tension** (1 à 5) — perspectives employeur, de « Très défavorable » à « Très favorable »

La page calcule et affiche également :
- L'**exposition moyenne pondérée** par le nombre de demandeurs d'emploi
- La **répartition des demandeurs** par tranche d'exposition
- L'**exposition moyenne par bande salariale** (< 25K, 25-35K, 35-50K, 50-75K, 75K+)
- L'**exposition par niveau d'études** (CAP/BEP, Bac, Bac+2, Bac+3, Bac+5/8)
- La **masse salariale exposée** : somme des salaires annuels des métiers très exposés (7+)

---

## Enseignements principaux

1. **Un tiers des métiers (20/61) sont très exposés (score 8+)**, concentrés dans les fonctions support, l'informatique, la communication et la finance. Ce sont des métiers majoritairement tertiaires, exercés sur ordinateur.

2. **Un autre tiers (18/61) est faiblement exposé (score 1-3)**, regroupant les métiers manuels du BTP, de l'agriculture, de la restauration et des services physiques. Ces métiers disposent d'une « barrière physique » naturelle à l'automatisation par l'IA.

3. **Le milieu de la distribution (scores 4-7) est plus hétérogène** : on y trouve des métiers hybrides comme la santé (médecins à 6, aide-soignants à 3), l'enseignement (6-7), et le management (5-7), où l'IA augmente la productivité sans remplacer la composante humaine.

4. **La corrélation exposition-salaire est notable** : les métiers les mieux rémunérés (informatique, finance, droit) sont aussi les plus exposés, tandis que les moins payés (nettoyage, restauration) sont les moins exposés. L'IA impacte en priorité les « cols blancs ».

5. **Le seul métier à 10/10 est le téléconseil/télévente**, un travail entièrement numérique et routinier que l'IA conversationnelle peut déjà largement automatiser.

---

## Limites

- **Panel de 61 métiers** sur les ~530 fiches ROME existantes — représentatif mais non exhaustif
- Le scoring repose sur un **modèle de langage unique** (Gemini Flash) avec un prompt calibré — un autre modèle ou prompt pourrait produire des scores légèrement différents
- Les données salariales et d'emploi proviennent de l'API France Travail et reflètent un **instantané** du marché, pas une tendance
- L'exposition mesure le **potentiel technique** de transformation, pas la vitesse réelle d'adoption (qui dépend du droit du travail, des conventions collectives, de l'acceptation sociale)
