# Valoria Vision — R7.2 Correctifs Lot 3
## UX import et gestion des comptes bancaires

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Objectif

Regrouper les prochains correctifs à forte valeur utilisateur avant une nouvelle archive installable.

Ce lot couvre deux besoins prioritaires exprimés en recette :

1. rendre l'import bancaire visuellement explicite pendant le traitement ;
2. permettre la modification et la suppression contrôlée des comptes bancaires.

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

## Partie C — Suppression contrôlée des comptes bancaires

### Comportement attendu

Ajouter une action `Supprimer le compte` ou équivalent.

### Règles de sécurité

- Si le compte ne contient aucune transaction, aucune récurrence et aucun import lié : suppression possible après confirmation.
- Si le compte contient des transactions, imports, récurrences ou éléments de rapprochement : ne pas supprimer directement.
- Dans ce cas, proposer plutôt l'archivage ou bloquer la suppression avec un message clair.

### Message attendu en cas de blocage

`Ce compte contient des données liées. Pour préserver l'historique, il ne peut pas être supprimé directement. Vous pouvez le passer au statut Archivé.`

---

## Tests à prévoir

- Créer un compte avec N° de compte / RIB et IBAN.
- Vérifier le masquage en liste, cartes, volet détail et import.
- Modifier uniquement les champs autorisés.
- Vérifier que le solde initial et la date initiale ne changent pas.
- Vérifier que l'import SG continue à reconnaître le bon compte.
- Supprimer un compte vide.
- Tenter de supprimer un compte avec transactions : suppression refusée ou archivage proposé.
- Vérifier que les soldes et listes restent cohérents après modification ou archivage.

---

## Statut

Statut : **à développer — prioritaire avant prochaine archive installable**.

Décision : regrouper ces corrections avec les corrections UX import avant de reconstruire une nouvelle archive.