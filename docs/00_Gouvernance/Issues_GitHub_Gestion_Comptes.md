# Issues GitHub - Gestion complète des comptes bancaires

Ce document contient les textes prêts à copier dans GitHub.

## Organisation recommandée

- **Epic parente** : Gestion complète des comptes bancaires.
- **Bug de recette** : rattaché à la campagne corrective R7.x.
- **Fonctionnalités et améliorations** : rattachées à la version V0.6.7.
- **Sub-issues** : toutes les issues ci-dessous, sauf le bug déjà créé séparément si une issue équivalente existe.

---

# 1. Epic parente

## Titre

```text
[EPIC] Gestion complète des comptes bancaires
```

## Description

```markdown
## Objectif

Compléter et sécuriser la gestion des comptes bancaires dans Valoria Vision.

L'utilisateur doit pouvoir créer, consulter, modifier, archiver, restaurer et, lorsque cela est sans risque, supprimer un compte bancaire. Toutes les listes de comptes utilisées par les autres modules doivent rester synchronisées sans redémarrage de l'application.

## Principes métier validés

- Le solde actuel est toujours calculé automatiquement.
- Le solde actuel ne peut pas être modifié directement.
- Le solde initial et sa date de référence restent modifiables via une action dédiée, avec recalcul des soldes.
- Un compte contenant un historique ne doit pas être supprimé physiquement : il doit être archivé.
- La suppression définitive est réservée aux comptes sans transaction, import, rapprochement, récurrence ou historique lié.
- Les actions principales sont accessibles par menu contextuel, au clic droit et via un bouton ⋮.
- Toute création, modification, archivage, restauration ou suppression doit être répercutée immédiatement dans tous les modules.

## Modules concernés

- Comptes
- Transactions et Imports
- Prévisionnel
- Rapprochements
- Budget
- Patrimoine
- Paramètres

## Critères de clôture de l'Epic

- Toutes les sub-issues sont terminées et validées en recette.
- Aucun redémarrage n'est nécessaire pour actualiser les listes de comptes.
- Les règles de calcul des soldes sont respectées.
- La suppression d'un compte contenant un historique est impossible.
- Les comptes archivés peuvent être filtrés et restaurés.
- La documentation et la matrice de recette sont à jour.
```

## Paramètres GitHub

- Type : Epic / Feature parente
- Priorité : P1
- Version cible : V0.6.7
- Labels recommandés : `epic`, `module:comptes`, `type:feature`, `priority:P1`

---

# 2. Bug de rafraîchissement détecté en recette

## Titre

```text
[BUG] Le module Rapprochements ne rafraîchit pas la liste des comptes après création
```

## Description

```markdown
## Contexte

Recette de la version V0.6.6-R7.1.

## Anomalie

Lorsqu'un nouveau compte est créé dans le module Comptes :

- le compte est correctement enregistré ;
- il apparaît immédiatement dans le module Comptes ;
- il n'apparaît pas dans la liste déroulante du module Rapprochements ;
- il devient visible uniquement après fermeture puis réouverture de Valoria Vision.

Le compte est donc bien persistant en base. Le défaut concerne le rafraîchissement de la liste ou du modèle de comptes conservé en mémoire.

## Étapes de reproduction

1. Ouvrir Valoria Vision.
2. Créer un nouveau compte bancaire.
3. Sans fermer l'application, ouvrir Rapprochements.
4. Dérouler la liste des comptes.
5. Constater que le nouveau compte est absent.
6. Fermer puis rouvrir l'application.
7. Retourner dans Rapprochements.
8. Constater que le compte est désormais présent.

## Résultat attendu

Le nouveau compte doit être disponible immédiatement dans Rapprochements et dans tous les sélecteurs de comptes, sans redémarrage.

## Critères d'acceptation

- Un compte créé apparaît immédiatement dans Rapprochements.
- Un compte renommé est immédiatement renommé dans tous les sélecteurs.
- Un compte archivé ou supprimé disparaît immédiatement des listes actives.
- Un compte restauré réapparaît immédiatement.
- Aucun doublon de compte n'est introduit lors du rafraîchissement.
- Le comportement persiste après redémarrage.

## Piste technique

Centraliser le chargement des comptes et diffuser un signal après toute création, modification, archivage, restauration ou suppression. Les écrans abonnés rechargent alors leur modèle de comptes.
```

## Paramètres GitHub

- Type : Bug
- Priorité : P1
- Sprint : R7.2, sauf décision d'intégration immédiate dans R7.1
- Labels recommandés : `bug`, `module:comptes`, `module:rapprochements`, `priority:P1`, `refresh`

---

# 3. Sub-issue - Menu contextuel

## Titre

```text
[FEATURE] Ajouter un menu contextuel complet sur les comptes bancaires
```

## Description

```markdown
## Besoin

Regrouper les actions liées à un compte dans un menu contextuel cohérent avec le standard UX de Valoria Vision.

## Menu attendu

- Ouvrir le détail
- Modifier le compte
- Voir les transactions
- Importer des opérations
- Mettre à jour le solde initial
- Archiver le compte ou Restaurer le compte
- Supprimer définitivement le compte, seulement lorsque l'action est autorisée

Le menu doit être accessible :

- au clic droit sur une ligne ou une carte ;
- par un bouton ⋮ visible pour les utilisateurs qui ne connaissent pas le clic droit.

## Critères d'acceptation

- Le menu s'ouvre sur la ligne ou la carte sélectionnée.
- Les actions concernent toujours le bon compte.
- Les actions indisponibles sont masquées ou désactivées avec une explication.
- Les actions destructives sont séparées visuellement.
- Le comportement est identique en vue tableau et en vue cartes.
```

- Priorité : P1
- Version cible : V0.6.7
- Labels : `type:feature`, `ux`, `module:comptes`, `priority:P1`

---

# 4. Sub-issue - Modification d'un compte

## Titre

```text
[FEATURE] Permettre la modification d'un compte bancaire
```

## Description

```markdown
## Besoin

Permettre la modification d'un compte existant depuis le menu contextuel.

## Champs modifiables

- Nom du compte
- Banque
- Type de compte
- Identifiant bancaire
- Devise lorsque la fonction sera activée
- Couleur ou icône lorsque ces propriétés seront disponibles
- Statut actif ou archivé via l'action dédiée

## Règles de solde

- Le solde actuel ne peut jamais être saisi ou modifié directement.
- Le solde initial et sa date de référence sont modifiables uniquement par l'action « Mettre à jour le solde initial ».
- Toute modification du solde initial ou de sa date déclenche un recalcul cohérent des soldes et indicateurs.

## Critères d'acceptation

- Le formulaire de création est réutilisé en mode modification et prérempli.
- Les contrôles de validité sont identiques à ceux de la création.
- Les changements sont visibles immédiatement dans tous les modules.
- La modification ne crée pas de compte en double.
- Les transactions et historiques restent liés au même compte.
- Les modifications persistent après redémarrage.
```

- Priorité : P1
- Version cible : V0.6.7
- Labels : `type:feature`, `module:comptes`, `priority:P1`

---

# 5. Sub-issue - Archivage et restauration

## Titre

```text
[FEATURE] Ajouter l'archivage et la restauration des comptes bancaires
```

## Description

```markdown
## Besoin

Permettre de retirer des listes de travail un compte clôturé ou inutilisé tout en conservant son historique.

## Comportement attendu

Un compte archivé :

- n'est plus proposé par défaut dans les nouvelles opérations ;
- disparaît des listes actives ;
- conserve ses transactions, imports, rapprochements et statistiques ;
- reste consultable dans l'historique et les rapports ;
- peut être restauré.

## Critères d'acceptation

- L'archivage demande une confirmation.
- Aucune donnée liée n'est supprimée.
- Le compte disparaît immédiatement des sélecteurs actifs.
- Le filtre Archivés permet de le retrouver.
- La restauration le rend immédiatement disponible.
- L'état archivé persiste après redémarrage.
```

- Priorité : P1
- Version cible : V0.6.7
- Labels : `type:feature`, `module:comptes`, `priority:P1`

---

# 6. Sub-issue - Suppression sécurisée

## Titre

```text
[FEATURE] Sécuriser la suppression définitive des comptes bancaires
```

## Description

```markdown
## Règle métier

La suppression définitive d'un compte est autorisée uniquement lorsque le compte ne possède aucun élément lié.

## Contrôles obligatoires

Avant suppression, vérifier l'absence de :

- transaction ;
- lot ou historique d'import ;
- occurrence ou rapprochement ;
- récurrence ou événement prévisionnel ;
- référence budgétaire ;
- historique de solde ou de valorisation ;
- autre donnée métier liée.

## Comportement attendu

- Si le compte est vide : confirmation renforcée puis suppression.
- Si le compte contient un historique : suppression refusée et proposition d'archivage.

## Message attendu

« Impossible de supprimer ce compte car il contient un historique. Vous pouvez l'archiver afin de conserver les données associées. »

## Critères d'acceptation

- Aucun enregistrement orphelin n'est créé.
- Aucun compte avec historique ne peut être supprimé.
- La suppression d'un compte vide est définitive après confirmation.
- Les listes et indicateurs sont actualisés immédiatement.
```

- Priorité : P1
- Version cible : V0.6.7
- Labels : `type:feature`, `module:comptes`, `data-integrity`, `priority:P1`

---

# 7. Sub-issue - Filtres Actifs / Archivés

## Titre

```text
[UX] Ajouter les filtres Tous / Actifs / Archivés dans la liste des comptes
```

## Description

```markdown
## Besoin

Permettre d'afficher séparément les comptes actifs et archivés.

## Filtres attendus

- Tous
- Actifs
- Archivés

## Critères d'acceptation

- Le filtre Actifs est utilisé par défaut.
- Le nombre de comptes affichés est cohérent avec le filtre.
- La recherche textuelle fonctionne avec le statut sélectionné.
- Un compte archivé ou restauré change immédiatement de liste.
- Le filtre reste lisible en vue tableau et en vue cartes.
```

- Priorité : P2
- Version cible : V0.6.7
- Labels : `ux`, `module:comptes`, `priority:P2`

---

# 8. Sub-issue technique - Synchronisation centrale

## Titre

```text
[TECH] Centraliser la synchronisation des comptes dans AccountService
```

## Description

```markdown
## Objectif technique

Éviter que chaque écran conserve une liste de comptes obsolète et supprimer la nécessité de redémarrer l'application.

## Comportement cible

Après une création, modification, archivage, restauration ou suppression :

1. la modification est enregistrée par le service de comptes ;
2. un événement ou signal de changement est diffusé ;
3. tous les écrans concernés rechargent leur modèle de comptes ;
4. la sélection courante est conservée lorsque cela reste possible.

## Modules abonnés

- Comptes
- Transactions et Imports
- Prévisionnel
- Rapprochements
- Budget
- Patrimoine
- Paramètres

## Critères d'acceptation

- Une seule source de vérité fournit les comptes.
- Aucun écran n'utilise durablement une liste initialisée uniquement au démarrage.
- Les rafraîchissements n'introduisent ni doublon ni clignotement bloquant.
- Les tests de création, modification, archivage, restauration et suppression passent sans redémarrage.
```

- Priorité : P1
- Version cible : V0.6.7
- Labels : `type:tech`, `module:comptes`, `architecture`, `priority:P1`

---

# 9. Sub-issue de tests transverses

## Titre

```text
[TEST] Ajouter des tests d'intégration transverses sur la gestion des comptes
```

## Description

```markdown
## Objectif

Vérifier que les opérations sur un compte sont répercutées dans tous les modules qui utilisent les comptes.

## Scénarios minimums

- Création d'un compte puis contrôle immédiat dans tous les sélecteurs.
- Modification du nom, de la banque, du type et de l'identifiant.
- Mise à jour du solde initial et contrôle des recalculs.
- Archivage puis contrôle de l'absence dans les listes actives.
- Restauration puis contrôle de la réapparition.
- Tentative de suppression d'un compte avec historique.
- Suppression d'un compte vide.
- Redémarrage puis contrôle de la persistance.

## Modules à contrôler

- Comptes
- Transactions et Imports
- Prévisionnel
- Rapprochements
- Budget
- Patrimoine
- Paramètres

## Critères d'acceptation

- Tous les scénarios sont ajoutés à la matrice de recette.
- Les résultats sont tracés par version.
- Toute anomalie détectée génère une issue liée.
```

- Priorité : P1
- Version cible : V0.6.7
- Labels : `type:test`, `qa`, `module:comptes`, `priority:P1`
