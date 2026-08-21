# Valoria Vision — R7.2 Lot 3
## Implémentation progression visuelle de l'import

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Objectif

Répondre au besoin exprimé en recette : l'import bancaire ne doit plus laisser l'utilisateur sans retour visuel pendant le traitement.

Avant :

```text
L'utilisateur cliquait sur Importer puis attendait sans indication claire.
```

Après ce correctif :

```text
Une fenêtre de progression affiche les étapes du traitement, les compteurs et l'état final.
```

---

## Fichiers ajoutés

| Fichier | Rôle |
|---|---|
| `app/r7_2/import_progress_patch.py` | Ajoute une fenêtre de progression pendant la validation d'un import |

## Fichiers modifiés

| Fichier | Modification |
|---|---|
| `main.py` | Active `apply_r7_2_import_progress_patch()` avant le feedback rapport |

---

## Étapes affichées

La progression affiche explicitement :

1. Préparation de l'import
2. Création du lot d'import
3. Écriture des opérations
4. Contrôle de cohérence du lot
5. Application des règles automatiques
6. Rapprochement prévisionnel
7. Rafraîchissement de l'interface
8. Import terminé

---

## Informations visibles

Pendant le traitement, l'utilisateur voit :

- fichier traité ;
- compte cible ;
- nombre de lignes traitées / total ;
- opérations importées ;
- doublons ;
- erreurs / rejets ;
- étape courante.

---

## Protection UX

Pendant le traitement :

- le bouton principal d'import est désactivé ;
- le bouton de validation d'import est désactivé ;
- le bouton d'aperçu est désactivé ;
- l'utilisateur ne peut pas relancer plusieurs imports simultanément par double clic.

---

## Compatibilité avec les correctifs précédents

Le correctif est activé avant `import_ui_feedback_patch`, ce qui permet de conserver :

- le message final d'import ;
- la génération automatique du rapport ;
- l'affichage du chemin du rapport ;
- le message spécifique en cas de fichier déjà importé à 100 %.

---

## Statut

Statut : **développé côté branche — à vérifier sur prochaine archive groupée Lot 3**.

Aucune archive installable n'a été reconstruite à ce stade, conformément à la décision de regrouper les correctifs.