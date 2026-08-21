# Valoria Vision — R7.2.3 Imports Fix
## Suivi des anomalies détectées en recette intermédiaire

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`  
Archive testée : `ValoriaVision_INSTALLABLE_V0_6_6_R7_2_3_IMPORTS_FIX`  
Date : 21/08/2026

---

## R7.2.3-ANO-001 — Titre de fenêtre resté en R7.2.2.1

| Champ | Valeur |
|---|---|
| Statut | À corriger |
| Gravité | Mineure |
| Domaine | Packaging / affichage version |
| Détecté par | Recette utilisateur |
| Contexte | L’archive R7.2.3 démarre correctement, mais le titre de fenêtre affiche encore `MVP V0.6.6-R7.2.2.1`. |
| Résultat obtenu | La version visible ne correspond pas à l’archive testée. |
| Résultat attendu | Le titre et les métadonnées visibles doivent afficher `V0.6.6-R7.2.3 — Imports Fix`. |
| Impact | Confusion de recette et de traçabilité. Non bloquant fonctionnellement. |
| Correctif attendu | Centraliser ou mettre à jour le libellé de version visible dans l’application et le packaging. |

---

## R7.2.3-ANO-002 — Identifiant de compte nouvellement créé non masqué

| Champ | Valeur |
|---|---|
| Statut | À corriger |
| Gravité | Moyenne côté confidentialité / UX |
| Domaine | Comptes bancaires / confidentialité affichage |
| Détecté par | Recette utilisateur |
| Contexte | Après création d’un compte `SG CC`, le tableau et/ou le volet détail affichent un identifiant long en clair ou partiellement en clair, contrairement aux comptes existants qui apparaissent sous forme `**** 5541`. |
| Résultat obtenu | Les comptes historiques affichent un identifiant masqué, mais le nouveau compte affiche une valeur brute ou trop détaillée, par exemple `FR763000300...` dans le tableau et l’identifiant long dans le volet détail. |
| Résultat attendu | Tous les identifiants de comptes doivent être affichés avec la même règle de masquage, quelle que soit leur origine : compte démo, compte existant, compte créé par l’utilisateur. |
| Impact | Incohérence UI et risque de confidentialité visuelle. Non bloquant pour poursuivre le développement correctif. |
| Correctif attendu | Appliquer systématiquement une fonction unique de masquage d’identifiant dans la liste des comptes, le volet détail, la vue cartes et les sélecteurs d’import si nécessaire. Le stockage complet en base reste autorisé pour la détection d’import. |

---

## Décision de recette

La R7.2.3 installable a permis de vérifier le démarrage et de révéler des anomalies utiles, mais elle ne constitue pas encore une version de recette complète.

Décision : poursuivre le développement correctif avant de dérouler une recette exhaustive.

Priorité de développement :

1. finaliser les correctifs Imports / Transactions ;
2. corriger les incohérences visibles déjà détectées ;
3. produire une nouvelle archive installable ;
4. recetter ensuite sur un périmètre stabilisé.
