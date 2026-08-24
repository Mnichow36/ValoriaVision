# Valoria Vision — Lot 5.1 UX Récurrences

## Objectif

Finaliser l'harmonisation UX de la fenêtre **Gérer les récurrences**.

La fenêtre était fonctionnelle, mais conservait encore des boutons techniques visibles en bas d'écran :

- Modifier ;
- Supprimer.

Cette présentation n'était plus cohérente avec la règle UX retenue pour Valoria Vision :

> Les actions techniques portant sur un élément existant doivent être accessibles via un menu contextuel sur la ligne concernée.

---

## Règle UX retenue

### Action globale

Le bouton **Ajouter** peut rester visible, car il crée un nouvel élément et ne dépend pas d'une ligne existante.

### Actions sur une récurrence existante

Les actions suivantes doivent être accessibles par clic droit sur une ligne de récurrence :

- Modifier la récurrence ;
- Supprimer la récurrence.

Le double-clic sur une ligne peut également rester un raccourci de modification.

---

## Comportement attendu

Dans la fenêtre **Gérer les récurrences** :

1. Le tableau liste les récurrences et événements prévisionnels.
2. Un clic droit sur une ligne ouvre un menu contextuel.
3. Le menu propose :
   - Modifier la récurrence ;
   - Supprimer la récurrence.
4. L'action Modifier ouvre le formulaire prérempli.
5. L'action Supprimer demande confirmation avant suppression.
6. Le tableau est rafraîchi après modification ou suppression.
7. Le prévisionnel parent est rafraîchi après fermeture ou action métier.

---

## État branche

La branche de développement active est :

`dev/r7.2-cdc-v1.1-imports-rapprochements`

La version visible devient :

`V0.6.6-R7.2.4 Lot 5.1 UX Récurrences`

---

## Recette ciblée

À vérifier dans la prochaine archive :

- le titre affiche bien `Lot 5.1 UX Récurrences` ;
- les boutons visibles `Modifier` et `Supprimer` ne sont plus présents ;
- le clic droit sur une récurrence affiche le menu contextuel ;
- Modifier fonctionne depuis le menu contextuel ;
- Supprimer fonctionne depuis le menu contextuel avec confirmation ;
- Ajouter reste accessible ;
- le prévisionnel est rafraîchi après action.

---

## Statut

Correctif final UX du Lot 5 : **programmé et marqué pour prochaine archive**.
