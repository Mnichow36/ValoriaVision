# Valoria Vision — Lot 5 — Prévisionnel / Récurrences

## Statut

Ouvert après validation ciblée du Lot 4.

Lot précédent validé :
- Lot 3 — Imports / Comptes / UX / Rapports / reconnaissance multi-banques
- Lot 4 — Cycle de vie imports / annulation / réimport / doublons

## Objectif du Lot 5

Stabiliser le module Prévisionnel et la gestion des récurrences avant le futur Lot 6 consacré aux rapprochements avancés.

Le Lot 5 doit rendre utilisable et cohérent le cycle suivant :

1. créer une récurrence ;
2. modifier une récurrence ;
3. supprimer ou désactiver une récurrence ;
4. gérer une date de fin ;
5. créer un événement ponctuel ;
6. générer des occurrences prévisionnelles cohérentes ;
7. afficher le prévisionnel sans double comptage ;
8. préparer les données nécessaires au futur rapprochement prévisionnel / réalisé.

## Périmètre fonctionnel

### 1. Gérer les récurrences

Le bouton `Gérer les récurrences` doit ouvrir une vraie interface de gestion.

L'utilisateur doit pouvoir :

- consulter les récurrences existantes ;
- créer une récurrence ;
- modifier une récurrence ;
- supprimer ou désactiver une récurrence ;
- filtrer par compte si possible ;
- visualiser le statut actif / inactif.

### 2. Champs attendus pour une récurrence

Une récurrence doit au minimum gérer :

- compte bancaire ;
- libellé ;
- catégorie ;
- montant ;
- fréquence ;
- prochaine date ;
- date de fin optionnelle ;
- scénario ;
- statut.

### 3. Fréquences attendues

Fréquences attendues :

- Mensuel ;
- Hebdomadaire ;
- Trimestriel ;
- Annuel ;
- Ponctuel.

La fréquence `Ponctuel` doit permettre de gérer un événement unique, sans génération répétée.

### 4. Occurrences prévisionnelles

Le Lot 5 doit préparer une génération plus propre des occurrences prévisionnelles.

Règles attendues :

- une récurrence active génère des occurrences futures ;
- une date de fin limite la génération ;
- un événement ponctuel ne génère qu'une occurrence ;
- les occurrences doivent être identifiables ;
- les occurrences futures doivent pouvoir être régénérées sans doublons ;
- les occurrences déjà rapprochées ou finalisées ne doivent pas être écrasées sans contrôle.

### 5. Prévisionnel et courbe

La courbe de trésorerie doit rester cohérente :

- prise en compte des récurrences actives ;
- respect de la période affichée ;
- respect du compte sélectionné ;
- absence de double comptage entre transaction réelle et occurrence prévisionnelle lorsque l'occurrence est déjà réalisée ou rapprochée ;
- lisibilité des libellés et dates.

## Hors périmètre du Lot 5

Le Lot 5 ne traite pas encore :

- rapprochement N↔N ;
- groupes de rapprochement ;
- validation manuelle avancée des écarts ;
- moteur complet de matching ;
- écarts montant/date avancés ;
- écran final de rapprochements avancés.

Ces sujets restent pour le Lot 6.

## Risques identifiés

- double comptage dans la courbe ;
- écrasement d'occurrences déjà rapprochées ;
- incohérence entre liste des récurrences et prévisionnel ;
- confusion entre récurrence et événement ponctuel ;
- bouton `Gérer les récurrences` visuellement présent mais non raccordé.

## Tests de recette ciblée prévus

### REC-L5-01 — Ouverture gestion récurrences

Depuis Prévisionnel, cliquer sur `Gérer les récurrences`.

Attendu : une fenêtre ou interface de gestion s'ouvre sans erreur.

### REC-L5-02 — Création récurrence mensuelle

Créer une récurrence mensuelle de test.

Attendu : la récurrence apparaît dans la liste et dans le prévisionnel.

### REC-L5-03 — Modification récurrence

Modifier montant, libellé ou date.

Attendu : la liste et le prévisionnel se mettent à jour.

### REC-L5-04 — Date de fin

Ajouter une date de fin.

Attendu : aucune occurrence ne doit être générée après cette date.

### REC-L5-05 — Événement ponctuel

Créer une opération ponctuelle.

Attendu : une seule occurrence est visible.

### REC-L5-06 — Suppression / désactivation

Supprimer ou désactiver une récurrence.

Attendu : elle ne doit plus alimenter le prévisionnel futur.

### REC-L5-07 — Filtre compte

Créer une récurrence sur un compte, puis changer le filtre compte.

Attendu : la récurrence n'apparaît que dans le bon périmètre.

### REC-L5-08 — Non régression imports

Après Lot 5, vérifier que les fonctionnalités validées en Lots 3 et 4 restent OK :

- import SG ;
- annulation import ;
- réimport ;
- doublons ;
- rapports.

## Critère de validation Lot 5

Le Lot 5 sera considéré comme validé si :

- le bouton `Gérer les récurrences` est opérationnel ;
- les récurrences peuvent être créées, modifiées, supprimées ou désactivées ;
- la date de fin est respectée ;
- les événements ponctuels fonctionnent ;
- le prévisionnel reste cohérent ;
- aucun comportement validé dans les Lots 3 et 4 ne régresse.
