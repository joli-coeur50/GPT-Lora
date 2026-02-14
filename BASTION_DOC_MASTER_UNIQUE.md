================================================================================
BASTION — DOC MASTER UNIQUE (AUTONOME / OFFLINE-FIRST / LINUX-FIRST / COFFRE)
Statut : DOCUMENT DE RÉFÉRENCE (contrat d’implémentation) — VERSION CANON SCELLÉE
Règle : ce document ne dépend d’aucun autre fichier, archive, projet ou historique.
Principe absolu : CE QUI N’EST PAS VÉRIFIABLE N’EXISTE PAS.
================================================================================

0) BUT DE CE DOCUMENT
- Donner une compréhension COMPLÈTE, CLAIRE, STRUCTURÉE et VÉRIFIABLE de BASTION.
- Servir de CONTRAT unique entre le besoin (Antoine) et l’implémentation (dev).
- Empêcher toute “simulation” : un succès = sortie réellement présente + preuves minimales.
- Encadrer ce qui est “prévu” (ROADMAP) vs ce qui existe (DONE).

Définitions rapides (vérifiables) :
- DONE : produit présent + tests OK + logs + report.
- SKIP : non requis dans le contexte (ex : FRIGO non défini), avec raison écrite.
- ERROR : échec propre (pas de crash brut), avec cause + action.
- ROADMAP : prévu mais NON garanti tant que pas implémenté et testé.

--------------------------------------------------------------------------------
1) VISION (UNE PHRASE)
BASTION est un COFFRE local autonome qui :
1) transforme un dossier d’images (INBOX) en datasets propres, notés, filtrés et adaptés (ATLAS),
2) entraîne des LoRA réellement utilisables (ENCLUME),
le tout en offline-first, avec logs temps réel (UI + terminal) et zéro cinéma.

--------------------------------------------------------------------------------
2) PÉRIMÈTRE (SCOPE) + DÉCISIONS STRUCTURANTES

2.1 Ce que BASTION EST
- Un outil local (UI web locale), conçu pour tourner sur Linux Mint.
- Un pipeline “dataset → LoRA” centré sur Stable Diffusion / SDXL.
- Un coffre autonome : toutes sorties, caches, logs, index, env, wheels, assets restent dans ./BASTION/.

2.2 Ce que BASTION N’EST PAS
- Pas un service cloud. Pas un serveur public.
- Pas une suite fourre-tout (galerie, marketplace, génération d’images, etc.).
- Pas une “démo” : aucune réussite fictive.

2.3 Modules retenus
- BASTION = ATLAS + ENCLUME uniquement.
- Tout module hors “dataset → LoRA” = HORS SCOPE tant qu’il n’est pas justifié et contractualisé ici.

2.4 “0 CHAOS / 0 BULLSHIT” = règles opérationnelles
- Mode SIMPLE par défaut.
- Mode AVANCÉ uniquement si nécessaire, caché/replié.
- Si une fonction n’est pas prête : “INDISPONIBLE” + explication + quoi faire, sans placebo.

2.5 DÉCISIONS PRISES PAR CE DOCUMENT (par défaut, modifiables uniquement via mise à jour du présent contrat)
Ces choix verrouillent la vérifiabilité. Si un dev propose autre chose : il doit modifier ce document + fournir preuves.

D2.5.1 Format LoRA final (ENCLUME)
- Sortie LoRA = fichier .safetensors (OBLIGATOIRE) + métadonnées minimales (voir Annexe C).
- Le fichier doit être chargeable via la lib safetensors (test scellage).

D2.5.2 Stockage index ATLAS / scans
- Index ATLAS = SQLite (OBLIGATOIRE) dans ./BASTION/DATA/INDEX_ATLAS/index.sqlite
- Objectif : incrémental fiable + gros volumes sans s’écrouler.

D2.5.3 Dédup ATLAS (pack core)
- Dédup CORE = pHash 64-bit + distance de Hamming (OBLIGATOIRE) + index.
- (Option) Dédup “précision” par embeddings = ROADMAP (voir Packs).

D2.5.4 Engine entraînement ENCLUME (référence)
- Référence par défaut : entraînement LoRA via “kohya-style sd-scripts” (appel subprocess) OU équivalent strictement documenté.
- EXIGENCE : reproductible offline après acquisition + logs live + artefact final exploitable.
- Si engine différent : doit prouver mêmes garanties (offline, logs, format, VRAM).

D2.5.5 Confinement technique (anti-écriture hors coffre)
- BASTION doit rediriger caches/tmp/config Python & libs vers ./BASTION/RUNTIME/ (liste env vars en Annexe B).
- Objectif : aucun fichier créé dans ~/, /tmp (sauf si TMP redirigé), ni dossiers cachés.

--------------------------------------------------------------------------------
3) CONTRAT COFFRE (NON NÉGOCIABLE)

3.1 Règle de confinement (écriture)
- BASTION n’écrit JAMAIS en dehors de ./BASTION/
- Toute écriture (logs, index, exports, env, caches, datasets, loras, reports) = dans :
  ./BASTION/DATA/ et ./BASTION/RUNTIME/

3.2 Entrées externes autorisées (LECTURE SEULE)
- INBOX : dossier d’images source (peut être n’importe où sur le disque).
- FRIGO : dossier de modèles (checkpoints, VAE, LoRA…), lecture seule.

3.3 Sorties internes (toujours dans le coffre)
- Datasets exportés (ATLAS) : ./BASTION/DATA/DATASETS/
- LoRA entraînées (ENCLUME) : ./BASTION/DATA/LORAS/
- Logs : ./BASTION/DATA/LOGS/
- Reports : ./BASTION/DATA/REPORTS/
- Index : ./BASTION/DATA/INDEX_*/   (dont INDEX_ATLAS)
- Bundles internes : ./BASTION/DATA/BUNDLES/
- Runtime (env + wheels + assets + tmp) : ./BASTION/RUNTIME/

3.4 Vérification (scellage)
- Un script “scellage” doit vérifier qu’aucun fichier n’a été écrit hors coffre.
- Le rapport doit sortir : OK / FAIL / SKIP, avec preuves (chemins) en cas de FAIL.

3.5 Confinement technique (OBLIGATOIRE)
But : empêcher les écritures “fantômes” des libs.
- BASTION doit forcer au runtime :
  - TMPDIR -> ./BASTION/RUNTIME/TMP/
  - HOME (optionnel mais recommandé) -> ./BASTION/RUNTIME/HOME/
  - XDG_* -> ./BASTION/RUNTIME/XDG/
  - caches ML (HF/torch/transformers/etc.) -> ./BASTION/RUNTIME/CACHES/
  - __pycache__ -> ./BASTION/RUNTIME/PYCACHE/ (via PYTHONPYCACHEPREFIX)
- Liste complète : Annexe B (ENV VARS + objectifs).

3.6 Interdits (critère FAIL scellage)
- Création/écriture dans :
  - ~/, ~/.cache, ~/.config, ~/.local, /tmp, /var/tmp
  - tout chemin hors ./BASTION/
Sauf :
- Lecture des entrées externes INBOX/FRIGO (lecture seule)

--------------------------------------------------------------------------------
4) OFFLINE-FIRST (À L’USAGE) / INSTALL INLINE

4.1 Principe
- L’USAGE (UI, ATLAS, lecture logs, manipulation datasets, ENCLUME) fonctionne SANS internet.
- L’acquisition (téléchargement) des dépendances/poids peut se faire UNE FOIS (si internet dispo), puis fonctionnement offline.

4.2 Architecture runtime
- Wheels (dépendances Python) : ./BASTION/RUNTIME/WHEELS/
- Environnement Python interne : ./BASTION/RUNTIME/ENV/
- Assets (poids modèles “outils”) : ./BASTION/RUNTIME/ASSETS/
- Verrouillage versions : ./BASTION/CONFIG/LOCK_VERSIONS.txt

4.3 “Install inline” (exigence UX)
- bastion.sh = point d’entrée unique.
- Si ENV absent → installation DANS LE COFFRE (pas d’install système globale).
- Si internet absent au premier run :
  - message clair : “ACQUISITION NÉCESSAIRE UNE FOIS” + commande courte.
- Après installation : usage offline = OK.

4.4 Offline strict (vérification)
- Pendant un job ATLAS/ENCLUME, BASTION ne doit ouvrir aucune connexion sortante non-locale.
- Scellage doit inclure un test “no outbound sockets” (voir Annexe F).

--------------------------------------------------------------------------------
5) EXIGENCES DE ROBUSTESSE (ANTI-PIÈGES)

5.1 Localhost / réseau / proxy
- BASTION fonctionne en local sans exposition réseau.
- Au lancement, bastion.sh neutralise les variables proxy pouvant casser localhost.
  (http_proxy, https_proxy, all_proxy, no_proxy, etc.)

5.2 Versions / incompatibilités
- Versions verrouillées.
- “Doctor” détecte incompatibilités et propose correction simple (pas de roman).

5.3 Anti-simulation
- ENCLUME n’annonce jamais une LoRA si le fichier final n’existe pas + tests charge OK.
- ATLAS n’annonce jamais “export réussi” si images/dataset.json/report/log ne sont pas présents.

5.4 Chemins avec espaces
- Tous chemins doivent être gérés via pathlib + quoting shell correct.
- Aucune hypothèse “pas d’espaces”.

--------------------------------------------------------------------------------
6) UX/UI — RÈGLES ET ÉCRANS

6.1 Forme générale
- UI web locale : simple, sobre, lisible.
- 3 écrans max : Emplacements / Atlas / Enclume
- Un panneau global Jobs/Logs accessible partout.

6.2 Temps réel (exigence)
- Tout job (ATLAS/ENCLUME) suivi en temps réel :
  - UI (progression + log live)
  - terminal (mode verbeux)
- UI et terminal lisent la MÊME vérité (même source de logs/statuts).

6.3 Page “Emplacements” (sources externes RO + vérifs)
- INBOX :
  - bouton “Parcourir…” si possible
  - fallback champ manuel
  - vérifs : existe / contient des images / accès OK
- FRIGO :
  - bouton “Parcourir…” si possible
  - fallback champ manuel
  - vérifs : existe / contient des modèles / accès OK
- COFFRE :
  - chemin affiché en lecture seule
  - bouton “Ouvrir”
- Boutons :
  - “Enregistrer”
  - “Rescanner tout”

6.4 “Rescanner tout”
- Re-scan INBOX : compteur + mise à jour
- Re-scan FRIGO : index modèles + mise à jour
- Re-scan datasets internes : mise à jour

6.5 Panneau Jobs/Logs (global)
- Liste jobs : RUNNING / DONE / ERROR / SKIP
- Pour un job :
  - progression (0–100)
  - étape courte
  - log live (auto-scroll)
  - actions : copier dernières lignes, ouvrir log, ouvrir dossier job

--------------------------------------------------------------------------------
7) ARCHITECTURE FONCTIONNELLE (ATLAS / ENCLUME)

7.1 Concepts clés
- INBOX : images source (lecture seule)
- FRIGO : modèles (lecture seule)
- DATASET : export interne (images copiées + metadata + report)
- JOB : exécution traçable (logs, status, report)

7.2 ATLAS (mission)
ATLAS transforme INBOX en DATASETS “PRÊTS LoRA” :
- détecte doublons, filtre qualité, attribue des scores,
- sélectionne les meilleures images selon objectifs,
- transforme (crop/resize/amélioration) si demandé,
- exporte un dataset propre et traçable.

7.3 ENCLUME (mission)
ENCLUME entraîne une LoRA RÉELLE à partir :
- d’un dataset exporté par ATLAS
- d’un modèle choisi dans FRIGO
et produit un artefact final exploitable + kit de test.

--------------------------------------------------------------------------------
8) ATLAS — SPEC COMPLÈTE

8.1 Entrée
- INBOX : dossier images (10 à très grand volume).
- Objectif sortie :
  - N images exactes OU %
- Paramètres (mode SIMPLE) :
  - Preset : Rapide / Équilibré / Qualité
  - Tolérance doublons : 1..10
  - Diversité : 1..5
- Paramètres (mode AVANCÉ, optionnel) :
  - poids scoring qualité vs esthétique vs diversité
  - options crop/resize
  - options enhance

8.2 Index incrémental (OBLIGATOIRE)
- ATLAS ne recalcule pas tout à chaque run.
- Index interne : ./BASTION/DATA/INDEX_ATLAS/index.sqlite
- Recalcul uniquement sur nouveaux/modifiés.

Identité fichier (règle de vérité) :
- Clé primaire image = sha256 du contenu (OBLIGATOIRE).
- Détection modif : (sha256) OU à défaut (mtime+size) déclenche recalcul hash.

8.3 Dedup (OBLIGATOIRE, CORE)
Objectif : pragmatique, rapide, ne s’effondre pas.
- Méthode CORE :
  - calcul pHash 64-bit pour chaque image
  - distance = Hamming(phashA, phashB)
  - regroupement doublons via seuil déterminé par “Tolérance 1..10”
- Tolérance 1..10 = seuil concret (distance max) :

  tol=1  -> max_dist=4   (strict)
  tol=2  -> max_dist=5
  tol=3  -> max_dist=6
  tol=4  -> max_dist=8
  tol=5  -> max_dist=10
  tol=6  -> max_dist=12
  tol=7  -> max_dist=14
  tol=8  -> max_dist=16
  tol=9  -> max_dist=18
  tol=10 -> max_dist=20  (permissif)

Règle de groupe :
- Dans un groupe de doublons, on garde le “meilleur” selon score qualité technique.
- Tous les doublons rejetés sont listés dans dataset.json + report (traçabilité).

8.4 Scoring qualité technique (OBLIGATOIRE)
But : éviter images inutiles pour LoRA.
Score_qualité (0..100) composé de :
- netteté / flou (pénalise flou)
- bruit / grain (pénalise bruit fort)
- compression / artefacts (pénalise)
- résolution (trop petite = pénalité)
- ratio / cadrage (hors presets = pénalité légère)
Chaque sous-score doit être loggé (au moins en mode avancé).

8.5 “Beauté / esthétique” (UTILE, PACK 40)
- Ce n’est PAS une vérité : filtre de préférence.
- Pondéré, désactivable, ne doit jamais écraser la qualité technique.
- UI : curseur simple + presets.

8.6 Tagging / captioning (UTILE, PACK 30)
- Captions/tags stockés DANS le DATASET exporté (coffre).
- Jamais d’écriture dans INBOX.

8.7 Transform (UTILE, PACK 50)
- Crop/resize SD-friendly :
  - règles sûres (ne pas massacrer le contenu)
  - normaliser ratio/résolution selon presets
- Preview recommandé : 12 images sample + scores.

8.8 Enhance (OPTIONNEL, PACK 60)
- Restauration/upscale si utile (coût élevé).
- OFF par défaut.

8.9 Sortie (export dataset) — FORMAT UNIQUE (OBLIGATOIRE)
./BASTION/DATA/DATASETS/atlas_<YYYYMMDD>_<RUNID>/
  images/               (copies des images sélectionnées)
  dataset.json          (liste, scores, tags/captions, chemins internes)
  report.txt            (résumé humain : params, stats, why)
  log.txt               (log détaillé)
  preview/              (optionnel : miniatures, grille)

8.10 Auto-liaison
- Après export : dataset visible immédiatement dans ENCLUME.
- Bouton “Envoyer à ENCLUME” auto-sélectionne le dataset.

8.11 Preuve de succès ATLAS (anti-cinéma)
DONE ATLAS uniquement si :
- dossier export existe
- images/ contient exactement N images attendues (ou % attendu ± règle définie)
- dataset.json présent et parse OK
- report.txt + log.txt présents
- report.txt contient :
  - paramètres
  - stats (scannées, rejetées, doublons, retenues)
  - top raisons de rejet (qualité/doublons/autres)

--------------------------------------------------------------------------------
9) ENCLUME — SPEC COMPLÈTE

9.1 Entrées
- Dataset : issu d’ATLAS (dropdown)
- Modèle : choisi depuis FRIGO (dropdown + recherche)
- Profil SIMPLE :
  - Low VRAM / Balanced / Quality
- Nom de sortie LoRA

9.2 Dry-run (OBLIGATOIRE)
- Bouton “Dry-run (vérifier)” :
  - vérifie dataset (images présentes, dataset.json cohérent)
  - vérifie modèle (accessible, lisible)
  - vérifie dépendances pack ENCLUME
  - estime VRAM et prévient si risque
Sans lancer l’entraînement.

9.3 Entraînement RÉEL (NON NÉGOCIABLE)
- ENCLUME doit produire une LoRA exploitable (.safetensors).
- Si impossible :
  - ERROR propre + explication + quoi faire
  - PAS de placebo, PAS de “success” fictif.

9.4 Sorties (run) — FORMAT UNIQUE (OBLIGATOIRE)
./BASTION/DATA/LORAS/<nom>_<YYYYMMDD>_<RUNID>/
  <nom>.safetensors     (OBLIGATOIRE)
  run.json              (params, versions, durée, chemins internes)
  report.txt            (résumé humain)
  log.txt               (détail)
  KIT_DE_TEST/
    README_TEST.md
    PROMPTS.txt
    REGLAGES_RECOMMANDES.txt
    CHEMINS.txt

9.5 Jobs/Logs (exigence)
- ENCLUME = job :
  RUNNING/DONE/ERROR + progression + étapes + log live UI/terminal

9.6 Preuve de succès ENCLUME (anti-cinéma)
DONE ENCLUME uniquement si :
- <nom>.safetensors existe ET taille > 0
- test charge safetensors OK
- run.json parse OK
- report.txt + log.txt présents
- KIT_DE_TEST présent + lisible

--------------------------------------------------------------------------------
10) DÉPENDANCES / RESSOURCES — STRATÉGIE PACKS

10.1 Pourquoi des packs
- Éviter le bloat et la fragilité.
- Garder un socle stable et activer les briques avancées uniquement si souhaité.

10.2 Packs (contrat)

PACK 00 — SOCLE (OBLIGATOIRE)
- UI + jobs + logs unifiés + doctor + scellage
- coffre strict + offline-first
- install reproductible (wheelhouse + lock versions)
- confinement technique (env vars)

PACK 10 — ATLAS CORE (OBLIGATOIRE)
- scan + index incrémental (sqlite) + dedup pHash + scoring technique + export dataset

PACK 20 — ENCLUME CORE (OBLIGATOIRE)
- entraînement LoRA réel + sortie .safetensors + kit test

PACK 30 — ATLAS TAGGING (UTILE, ROADMAP tant que pas livré)
- tagging/captioning auto (assets requis)

PACK 40 — ATLAS AESTHETIC (UTILE, ROADMAP tant que pas livré)
- scoring esthétique pondéré (assets requis)
- curseur + presets

PACK 50 — ATLAS TRANSFORM (UTILE, ROADMAP tant que pas livré)
- crop/resize SD-friendly + normalisation dataset + preview

PACK 60 — ATLAS ENHANCE (OPTIONNEL, ROADMAP tant que pas livré)
- restauration/upscale (coûteux), OFF par défaut

10.3 Assets Manager (OBLIGATOIRE)
- Centralise roues + poids dans le coffre.
- Statut : présent/absent
- Hash + licence + source dans manifest.
- Si absent : UI affiche “INDISPONIBLE” + instructions.

--------------------------------------------------------------------------------
11) CRITÈRES D’ACCEPTATION (DEFINITION OF DONE “CHEZ ANTOINE”)

A) BOOT / UI
[ ] ./BASTION/bastion.sh démarre l’UI localement sans crash.
[ ] Aucun besoin d’exposition réseau.
[ ] Proxies neutralisés pour localhost.
[ ] UI = 3 écrans max + panneau Jobs/Logs.
[ ] UI et terminal montrent les mêmes logs/statuts (même source).

B) COFFRE
[ ] Aucun fichier n’est écrit hors ./BASTION/.
[ ] INBOX/FRIGO jamais modifiés.
[ ] Confinement technique actif (caches/tmp/redirections).
[ ] scellage détecte toute violation (FAIL avec chemins).

C) OFFLINE-FIRST
[ ] Après install, l’UI, ATLAS, ENCLUME fonctionnent sans internet.
[ ] LOCK_VERSIONS.txt présent.
[ ] scellage inclut test “pas de connexions sortantes non-locales”.

D) ATLAS
[ ] Index incrémental (ne recalcule pas tout à chaque run).
[ ] Dédup fonctionnel (tolérance 1..10 a un effet mesurable).
[ ] Export dataset RÉEL (images + dataset.json + report + log).
[ ] Dataset apparaît immédiatement dans ENCLUME.

E) ENCLUME
[ ] Dry-run valide sans entraîner.
[ ] Entraînement réel produit une sortie exploitable OU échoue proprement.
[ ] Run complet : run.json + report + log + KIT_DE_TEST.
[ ] LoRA .safetensors charge OK.

F) SCELLAGE
[ ] LAUNCH/bastion_scellage.sh produit un rapport OK/FAIL/SKIP lisible.
[ ] Produit un “bundle de distribution” interne au coffre (sans données perso).

--------------------------------------------------------------------------------
12) SCRIPTS EXIGÉS (NOMS ET RÔLES)

- bastion.sh
  - point d’entrée unique
  - lance UI
  - applique confinement env vars + neutralise proxy
  - installe inline si ENV absent

- LAUNCH/bastion_doctor.sh
  - diagnostic court OK/FAIL :
    - python/venv, libs clés, GPU, espace disque, chemins, packs, assets, locks

- LAUNCH/bastion_scellage.sh
  - check coffre + mini tests + bundle de distribution
  - inclut :
    - vérif “no-write outside”
    - vérif offline (no outbound)
    - tests parse/charge (dataset.json, run.json, safetensors)
    - génération bundle

(Optionnel mais recommandé si acquisition séparée)
- LAUNCH/bastion_acquire_online.sh
  - télécharge wheels/assets nécessaires dans ./BASTION/RUNTIME/
  - écrit manifest hashes + sources + licences

--------------------------------------------------------------------------------
13) WORKFLOW UTILISATEUR (SIMPLE)

1) Lancer : ./BASTION/bastion.sh
2) Emplacements : définir INBOX + FRIGO (lecture seule) → Enregistrer
3) ATLAS : choisir objectif (N ou %) + preset → Lancer → export dataset
4) ENCLUME : choisir dataset + modèle FRIGO + profil → Dry-run → Lancer → LoRA réelle
5) Tester : utiliser KIT_DE_TEST
6) Sceller : LAUNCH/bastion_scellage.sh → bundle de distribution

--------------------------------------------------------------------------------
14) ROADMAP (prévu, NON garanti tant que non implémenté + testé)
- Pack TAGGING (captioning auto)
- Pack AESTHETIC (score pondéré)
- Pack TRANSFORM (crop/resize SD-friendly + preview)
- Pack ENHANCE (upscale/restauration)
Règle : chaque pack activable, OFF par défaut, ne casse jamais le socle.

--------------------------------------------------------------------------------
15) ANTI-SIMULATION (CLAUSES)
- Interdit de générer des “preuves” (placebo).
- DONE = sortie vérifiable (dataset export réel / LoRA réelle / logs & reports).
- SKIP = cas non requis + explication.
- ERROR = échec propre, pas de crash brut, pas de mensonge.

--------------------------------------------------------------------------------
16) NOTE MACHINE (CONTEXTE EXECUTION)
Cible : Linux Mint (Cinnamon), machine d’Antoine.
GPU : RTX 2070 SUPER 8GB → profils Low VRAM requis.
Stockage : INBOX et FRIGO peuvent être externes, chemins avec espaces.
Le projet doit tolérer les chemins avec espaces.

================================================================================
ANNEXES (FAITS VÉRIFIABLES / FORMATS / PREUVES)
================================================================================

ANNEXE A — CONVENTIONS DE CHEMINS (OBLIGATOIRE)
- Tous chemins stockés dans les JSON = chemins RELATIFS AU COFFRE quand c’est interne.
- Pour la traçabilité INBOX :
  - stocker “source_rel” (chemin relatif à la racine INBOX choisie)
  - NE PAS stocker le chemin absolu utilisateur dans les exports (évite fuite de données)

ANNEXE B — ENV VARS CONFINEMENT (OBLIGATOIRE)
Objectif : forcer caches/tmp/config dans ./BASTION/RUNTIME/

À fixer au lancement (au minimum) :
- TMPDIR=./BASTION/RUNTIME/TMP
- XDG_CACHE_HOME=./BASTION/RUNTIME/XDG/cache
- XDG_CONFIG_HOME=./BASTION/RUNTIME/XDG/config
- XDG_DATA_HOME=./BASTION/RUNTIME/XDG/data
- PYTHONPYCACHEPREFIX=./BASTION/RUNTIME/PYCACHE
- HF_HOME=./BASTION/RUNTIME/CACHES/huggingface
- TRANSFORMERS_CACHE=./BASTION/RUNTIME/CACHES/transformers
- TORCH_HOME=./BASTION/RUNTIME/CACHES/torch
- MPLCONFIGDIR=./BASTION/RUNTIME/CACHES/matplotlib

Recommandé (selon libs) :
- CUDA_CACHE_PATH=./BASTION/RUNTIME/CACHES/cuda
- NUMBA_CACHE_DIR=./BASTION/RUNTIME/CACHES/numba
- HOME=./BASTION/RUNTIME/HOME (si isolation max souhaitée)

ANNEXE C — FORMAT MINIMUM `dataset.json` (OBLIGATOIRE)
Structure (exemple minimal) :

{
  "bastion_version": "X.Y.Z",
  "atlas_run_id": "atlas_YYYYMMDD_RUNID",
  "created_at": "YYYY-MM-DDTHH:MM:SS",
  "inbox_signature": {
    "root_name": "basename_inbox",
    "file_count_scanned": 12345
  },
  "params": {
    "preset": "balanced",
    "target_mode": "count|percent",
    "target_value": 500,
    "dedup_tolerance": 6,
    "diversity": 3
  },
  "stats": {
    "scanned": 12345,
    "kept": 500,
    "rejected_quality": 2000,
    "rejected_duplicates": 5000
  },
  "items": [
    {
      "image_rel": "images/000001.jpg",
      "source_rel": "subdir/original_name.jpg",
      "sha256": "…",
      "phash64": "…",
      "scores": {
        "quality": 87.2,
        "aesthetic": null,
        "diversity": 0.63
      },
      "tags": [],
      "caption": ""
    }
  ]
}

ANNEXE D — FORMAT MINIMUM `run.json` ENCLUME (OBLIGATOIRE)
{
  "bastion_version": "X.Y.Z",
  "enclume_run_id": "enclume_YYYYMMDD_RUNID",
  "created_at": "YYYY-MM-DDTHH:MM:SS",
  "dataset_ref": "DATA/DATASETS/atlas_YYYYMMDD_RUNID",
  "base_model_ref": {
    "frigo_rel": "checkpoints/model.safetensors",
    "sha256": "…"
  },
  "profile": "low_vram|balanced|quality",
  "engine": "kohya_sd_scripts|OTHER",
  "params": {
    "epochs": 10,
    "batch": 1,
    "resolution": 1024,
    "lr": 1e-4
  },
  "outputs": {
    "lora_file": "<nom>.safetensors",
    "lora_sha256": "…"
  },
  "duration_sec": 12345,
  "status": "DONE|ERROR"
}

ANNEXE E — LOGS (SOURCE UNIQUE)
- Chaque job écrit un log fichier : log.txt dans son dossier run.
- Un index logs global (optionnel) : ./BASTION/DATA/LOGS/jobs.jsonl
- UI et terminal ne “devinent” rien : ils lisent ces fichiers/streams.

ANNEXE F — PREUVES SCELLAGE / DOCTOR (MINI TESTS)
Doctor (bastion_doctor.sh) doit vérifier :
- venv présent, python ok, imports clés ok
- GPU détecté + VRAM affichée
- chemins INBOX/FRIGO (si configurés) accessibles en lecture
- LOCK_VERSIONS.txt présent
- packs requis présents

Scellage (bastion_scellage.sh) doit vérifier :
1) NO-WRITE-OUTSIDE :
   - scan des fichiers récents depuis lancement (ou journal interne)
   - FAIL si écritures hors ./BASTION/
2) OFFLINE (no outbound) :
   - pendant un job court, vérifier absence de sockets sortantes non-locales
   - FAIL si connexion externe détectée
3) PREUVES ATLAS :
   - dataset export réel + parse dataset.json + compte images
4) PREUVES ENCLUME :
   - si une LoRA existe : test charge safetensors + présence kit test
   - sinon SKIP avec raison
5) BUNDLE :
   - créer ./BASTION/DATA/BUNDLES/bastion_bundle_YYYYMMDD_RUNID/
   - inclure scripts, configs, lock, manifests, UI (sans données perso)
   - exclure INBOX paths absolus, datasets privés, loras privées (sauf option explicite)

================================================================================
FIN — CE DOCUMENT EST LE CONTRAT UNIQUE
Toute implémentation BASTION doit respecter :
- Coffre strict (y compris caches/tmp)
- Offline-first à l’usage + vérification no-outbound
- ATLAS pro dataset (incrémental, dedup concret, export réel)
- ENCLUME LoRA réelle (.safetensors + tests)
- Logs temps réel UI + terminal (même source)
- Zéro cinéma
================================================================================
