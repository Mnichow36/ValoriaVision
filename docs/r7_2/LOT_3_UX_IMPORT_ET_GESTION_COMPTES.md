# Valoria Vision — R7.2 Correctifs Lot 3
## UX import et gestion des comptes bancaires

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Objectif

Regrouper les prochains correctifs à forte valeur utilisateur avant une nouvelle archive installable.

Ce lot couvre trois besoins prioritaires exprimés en recette :

1. rendre l'import bancaire visuellement explicite pendant le traitement ;
2. permettre la modification et la suppression contrôlée des comptes bancaires ;
3. préparer la reconnaissance internationale des IBAN en vue d'une future gestion multi-devises / Premium.

Aucune nouvelle archive ne doit être reconstruite pour chaque sous-correctif mineur. Les correctifs seront regroupés puis livrés dans une archive de recette cohérente.

---

## Partie A — UX de progression pendant l'import

### Problème constaté

L'import est actuellement trop austère : l'utilisateur clique sur importer puis attend sans information suffisante sur l'état réel du traitement.

### Comportement attendu

Ajouter une interface de progression comprenant :

- barre de progression ;
- étape en cours ;
- fichier traité ;
- compte cible ;
- nombre de lignes traitées / total ;
- compteurs visibles : nouvelles, doublons, erreurs, rejets ;
- message final clair ;
- blocage ou protection contre double clic pendant le traitement.

### Étapes à afficher

1. Analyse du fichier
2. Détection du format bancaire
3. Identification du compte source
4. Lecture des opérations
5. Contrôle des doublons
6. Préparation du lot d'import
7. Écriture en base
8. Application des règles automatiques
9. Génération du rapport d'import
10. Import terminé

Statut : **à développer**.

---

## Partie B — Modification contrôlée des comptes bancaires

### Demande métier

Permettre à l'utilisateur de modifier un compte bancaire existant, mais uniquement sur les champs d'identité et de présentation.

### Champs modifiables

Les champs modifiables sont :

- Nom du compte ;
- Banque ;
- Type ;
- N° de compte / RIB ;
- IBAN ;
- Devise ;
- Statut.

### Champs non modifiables dans cet écran

Les champs suivants ne doivent pas être modifiés dans l'écran de modification standard :

- Solde initial ;
- Date initiale.

Ces deux champs doivent rester gérés par l'action dédiée : `Mettre à jour le solde initial`.

### Implémentation ajoutée

- Ajout du patch `app/r7_2/account_management_patch.py`.
- Ajout des colonnes `accounts.account_number` et `accounts.iban` par migration légère.
- Maintien du champ historique `accounts.identifier` pour compatibilité avec le moteur d'import existant.
- Ajout d'un formulaire de compte avec `N° de compte / RIB` et `IBAN`.
- Ajout d'une action `Modifier le compte` dans le volet détail.
- La modification d'identité ne touche pas au solde initial ni à la date initiale.
- Correction de la méthode `update_account`, qui utilisait auparavant une variable non définie.

Statut : **développé côté branche — à vérifier sur prochaine archive installable**.

---

## Évolution du formulaire de compte

### Ancien champ

`Identifiant`

### Nouveaux champs attendus

1. `N° de compte / RIB`
2. `IBAN`

### Règles d'affichage

- Les deux valeurs peuvent être stockées complètes en base pour permettre le rapprochement avec les fichiers bancaires.
- Les deux valeurs doivent être masquées dans les tableaux, cartes, volets de détail et sélecteurs.
- L'IBAN doit être affiché de manière masquée, par exemple : `FR7630...84255`.
- Le N° de compte / RIB doit être affiché de manière masquée, par exemple : `**** 5529`.

### Règles de validation

- Le champ `N° de compte / RIB` accepte un identifiant court ou partiel utile aux imports bancaires.
- Le champ `IBAN` doit accepter un IBAN au format IBAN.
- L'application doit normaliser les espaces dans l'IBAN.
- Une alerte doit être affichée si l'IBAN semble invalide, sans bloquer les cas de recette si la banque exporte un identifiant incomplet.

---

## Partie C — Reconnaissance internationale des IBAN

### Demande métier

Dans la perspective d'une future gestion multi-devises et d'un module Premium, Valoria Vision doit pouvoir reconnaître tous les IBAN, et pas uniquement les IBAN français.

### Comportement attendu

Le champ `IBAN` doit accepter et normaliser les IBAN internationaux conformes à la structure IBAN :

- deux lettres de pays ;
- deux chiffres de contrôle ;
- suite alphanumérique BBAN ;
- longueur variable selon le pays ;
- espaces autorisés à la saisie mais supprimés/normalisés au stockage.

### Exemples à accepter

- France : `FR76 3000 3038 9000 0503 8425 5`
- Allemagne : `DE89 3704 0044 0532 0130 00`
- Espagne : `ES91 2100 0418 4502 0005 1332`
- Italie : `IT60 X054 2811 1010 0000 0123 456`
- Belgique : `BE68 5390 0754 7034`
- Suisse : `CH93 0076 2011 6238 5295 7`
- Royaume-Uni : `GB29 NWBK 6016 1331 9268 19`
- Pologne : `PL61 1090 1014 0000 0712 1981 2874`

### Validation ajoutée

- Normalisation des espaces et séparateurs.
- Vérification structurelle internationale.
- Vérification mod 97 pour les IBAN complets.
- Alerte non bloquante en interface si l'IBAN semble invalide.
- Le champ `N° de compte / RIB` reste utilisable pour les identifiants partiels issus des exports bancaires.

### Lien avec les devises

Le pays de l'IBAN ne doit pas imposer automatiquement la devise du compte.

Exemples :

- un compte français peut être en EUR ;
- un compte suisse peut être en CHF ou EUR ;
- un compte britannique peut être en GBP ou EUR ;
- un compte multi-devises peut exister avec une devise principale sélectionnée par l'utilisateur.

Le champ `Devise` reste donc explicitement modifiable et indépendant de l'IBAN.

### Limite du Lot 3

Le Lot 3 prépare la structure et la validation IBAN internationale, mais ne met pas encore en œuvre la conversion automatique des devises, les taux de change, ni les valorisations multi-devises. Ces éléments relèvent d'un futur module Premium.

Statut : **développé côté branche — à vérifier sur prochaine archive installable**.

---

## Partie D — Suppression contrôlée des comptes bancaires

### Comportement attendu

Ajouter une action `Supprimer le compte` ou équivalent.

### Règles de sécurité

- Si le compte ne contient aucune transaction, aucune récurrence et aucun import lié : suppression possible après confirmation.
- Si le compte contient des transactions, imports, récurrences ou éléments de rapprochement : ne pas supprimer directement.
- Dans ce cas, proposer plutôt l'archivage ou bloquer la suppression avec un message clair.

### Message attendu en cas de blocage

`Ce compte contient des données liées. Pour préserver l'historique, il ne peut pas être supprimé directement. Vous pouvez le passer au statut Archivé.`

### Implémentation ajoutée

- Ajout d'une action `Supprimer / archiver` dans le volet détail.
- Suppression autorisée uniquement pour un compte sans transaction, import, récurrence ou occurrence prévisionnelle.
- Si des données liées existent, proposition d'archivage au lieu d'une suppression directe.

Statut : **développé côté branche — à vérifier sur prochaine archive installable**.

---

## Tests techniques ajoutés

- `tools/test_r7_2_account_management.py`

Ce test vérifie :

- normalisation IBAN ;
- validation mod 97 France / Allemagne / Suisse ;
- rejet d'un IBAN à clé invalide ;
- création d'un compte avec N° de compte / RIB et IBAN ;
- stockage séparé de `account_number` et `iban` ;
- conservation de `identifier` pour les imports ;
- modification des champs autorisés ;
- non-modification du solde initial et de la date initiale ;
- suppression d'un compte vide.

---

## Tests à prévoir en recette utilisateur

- Créer un compte avec N° de compte / RIB et IBAN.
- Vérifier le masquage en liste, cartes, volet détail et import.
- Modifier uniquement les champs autorisés.
- Vérifier que le solde initial et la date initiale ne changent pas.
- Vérifier que l'import SG continue à reconnaître le bon compte.
- Saisir des IBAN français et internationaux valides.
- Vérifier que les IBAN sont normalisés et masqués.
- Vérifier que le pays de l'IBAN ne force pas automatiquement la devise.
- Supprimer un compte vide.
- Tenter de supprimer un compte avec transactions : suppression refusée ou archivage proposé.
- Vérifier que les soldes et listes restent cohérents après modification ou archivage.

---

## Statut global du Lot 3

- UX progression import : **à développer**.
- Gestion comptes RIB / IBAN / édition / suppression contrôlée : **développée côté branche**.
- Prochaine archive : **à reconstruire uniquement après fin du Lot 3 complet**.
