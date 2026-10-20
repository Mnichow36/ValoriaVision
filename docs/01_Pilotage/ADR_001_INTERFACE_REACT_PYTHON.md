# ADR-001 — Prototype d’interface React sur moteur Python

**Statut :** prototype isolé  
**Issue :** #154  
**Branche :** `feat/react-poc-foundation`  
**Base :** `release/r8-test-21`

## Décision

Tester une interface React/TypeScript consommant une API Python locale, sans
modifier les moteurs métier ni supprimer l’interface PySide existante.

## Principes

- Python reste la source de vérité pour les calculs et les écritures.
- React assure uniquement la présentation et les interactions utilisateur.
- SQLite et le coffre local restent dans le périmètre Python.
- L’API écoute uniquement sur `127.0.0.1`.
- L’API ne crée jamais automatiquement une nouvelle base pour satisfaire une
  requête de l’interface.
- Les données de démonstration et les données personnelles ne sont pas incluses
  dans le frontend.
- Le shell Tauri choisit un port local dynamique, démarre le moteur Python et
  l’arrête avec l’application.
- Le mot de passe maître reste vérifié par Python. Le frontend conserve seulement
  en mémoire un jeton opaque, limité par le délai d’inactivité existant.
- Tauri génère à chaque lancement un secret d’amorçage aléatoire transmis au
  processus Python ; l’API refuse les clients locaux qui ne le présentent pas.

## Pourquoi partir de TEST21

TEST22 est encore porté par une Pull Request brouillon et ne constitue pas une
référence validée. Le prototype doit rester indépendant de sa recette. Les
correctifs validés ultérieurement seront repris explicitement.

## Première coupe verticale

1. contrôle de santé de l’API ;
2. contrat Dashboard en lecture seule ;
3. composants visuels R8 réutilisables ;
4. gestion explicite du chargement et de l’indisponibilité du moteur ;
5. test Python du contrat sans dépendance à PySide ou FastAPI.

## Points restant avant distribution

- production du sidecar Python Windows avec PyInstaller ;
- inclusion et signature du sidecar dans le package Tauri ;
- limitation persistante des tentatives de déverrouillage ;
- renouvellement automatique de l’écran lorsque la session expire ;
- package Windows autonome et signé ;
- tests E2E sur package ;
- validation de la persistance après deux démarrages ;
- décision de remplacement progressif des écrans PySide.
