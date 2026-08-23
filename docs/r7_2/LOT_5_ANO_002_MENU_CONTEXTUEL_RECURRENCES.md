# Lot 5 — ANO-002 — Menu contextuel récurrences non conforme

## Constat recette utilisateur

Dans la fenêtre **Prévisionnel > Gérer les récurrences**, les actions fonctionnelles sont opérationnelles, mais restent exposées sous forme de boutons visibles en bas de fenêtre :

- Ajouter
- Modifier
- Supprimer

Or la règle UX validée pour Valoria Vision est de privilégier les actions techniques via **menu contextuel clic droit**, comme cela a été fait pour les comptes.

## Statut

NOK UX — non bloquant métier, mais bloquant pour validation complète du Lot 5.

## Comportement attendu

- Clic droit dans la table : menu contextuel avec **Ajouter**, **Modifier**, **Supprimer**.
- Double-clic sur une ligne : modification.
- Aucun bouton technique visible en bas de fenêtre.
- Bouton visible conservé : **Fermer** uniquement.

## Décision

Corriger le patch Lot 5 pour supprimer les boutons visibles Ajouter / Modifier / Supprimer et raccorder les actions au menu contextuel.
