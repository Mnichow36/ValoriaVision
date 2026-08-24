# Valoria Vision — Lot 5.2
## Simplification UX de l'écran Prévisionnel

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Contexte

Lors de la recette de l'écran Prévisionnel, deux incohérences UX restantes ont été relevées :

1. le bouton bleu `+ Ajouter événement / récurrence` en haut de l'écran fait doublon avec la fenêtre `Gérer les récurrences` ;
2. le menu contextuel de la courbe propose `Voir les opérations de cette période`, alors que ces opérations sont déjà visibles au survol et accessibles au clic.

Ces deux points créent une surcharge inutile et nuisent à l'harmonisation des écrans.

---

## Décision UX

### Ajout / gestion des événements prévisionnels

Le point d'entrée unique devient :

`Gérer les récurrences`

Depuis cette fenêtre, l'utilisateur peut :

- ajouter un événement ou une récurrence ;
- modifier une récurrence via menu contextuel ;
- supprimer une récurrence via menu contextuel.

Le bouton bleu `+ Ajouter événement / récurrence` de l'écran Prévisionnel est supprimé / masqué.

### Menu contextuel de la courbe

Le menu contextuel de la courbe ne doit plus servir à afficher les opérations de la période.

Règles :

- survol : détail des opérations ;
- clic : détail de la période ;
- clic droit : uniquement gestion des récurrences existantes ;
- s'il n'y a aucune récurrence sur la période, aucun menu contextuel utile n'est affiché.

---

## Implémentation

Ajout du patch :

`app/r7_2/forecast_ux_simplification_patch.py`

Activation dans :

`main.py`

Version visible :

`V0.6.6-R7.2.4 Lot 5.2 UX Prévisionnel`

---

## Contrôles de recette attendus

1. L'écran Prévisionnel ne doit plus afficher le bouton bleu `+ Ajouter événement / récurrence`.
2. Le bouton `Gérer les récurrences` doit rester visible et fonctionnel.
3. La fenêtre `Gérer les récurrences` doit permettre l'ajout.
4. Les actions Modifier / Supprimer doivent être disponibles par clic droit sur une récurrence.
5. Le survol de la courbe doit continuer à afficher les opérations.
6. Le clic sur une période doit continuer à ouvrir le détail.
7. Le clic droit sur une période sans récurrence ne doit plus afficher d'action inutile.
8. Le clic droit sur une période avec récurrence doit proposer uniquement les actions de gestion de cette récurrence.

---

## Statut

Développé côté branche. À vérifier dans la prochaine archive installable Lot 5.2.
