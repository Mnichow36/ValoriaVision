# Valoria Vision V0.6.6-R7.2.2 — Import Fix

Version corrective courte destinée à stabiliser le module **Transactions / Import bancaire** avant reprise du recettage approfondi des rapprochements.

## Corrections intégrées

- **R7.2-ANO-001 — P0** : contrôle du compte bancaire source détecté dans les exports Société Générale.
  - Extraction des identifiants présents dans les lignes techniques avant l'en-tête.
  - Extraction aussi depuis le nom du fichier lorsqu'il contient un numéro de compte.
  - Sélection automatique du compte Valoria si une correspondance fiable existe.
  - Blocage de l'import si le fichier contient un identifiant fiable qui ne correspond pas au compte sélectionné.

- **R7.2-ANO-002 — P1** : enrichissement des libellés importés.
  - Les paiements carte Société Générale utilisent désormais la colonne `Détail de l’écriture`.
  - Exemple : `CARTE X6425 18/06` devient `CARTE X6425 18/06 — SC-INTERMARCHE`.
  - Les règles automatiques peuvent donc matcher les commerçants réels.

- **R7.2-ANO-003 — P1** : affichage monétaire avec deux décimales.
  - Format homogène : `-26,58 €`, `1 200,00 €`.

- **R7.2-ANO-004 — P1** : affichage des dates au format français.
  - Format d'affichage : `JJ/MM/AAAA`.
  - Le stockage interne reste en ISO `AAAA-MM-JJ`.

- **R7.2-ANO-005 — P1** : filtre période Transactions remplacé par une logique `Du / Au`.
  - Deux sélecteurs calendaires.
  - Bouton `Toutes dates` pour revenir à l'affichage complet.

## Non modifié

- Le moteur Rapprochements n'est pas refondu dans cette version.
- La création de règles depuis transaction reste considérée comme OK fonctionnel après vérification utilisateur.
- GitHub reste hors périmètre tant que l'accès distant n'est pas disponible.
