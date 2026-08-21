# Valoria Vision — R7.2.3 Imports Fix
## Suivi des anomalies détectées en recette intermédiaire

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`  
Archive testée : `ValoriaVision_INSTALLABLE_V0_6_6_R7_2_3_IMPORTS_FIX`  
Date : 21/08/2026

---

## R7.2.3-ANO-001 — Titre de fenêtre resté en R7.2.2.1

| Champ | Valeur |
|---|---|
| Statut | Corrigé dans la branche de développement — à vérifier sur prochaine archive |
| Gravité | Mineure |
| Domaine | Packaging / affichage version |
| Détecté par | Recette utilisateur |
| Contexte | L’archive R7.2.3 démarrait correctement, mais le titre de fenêtre affichait encore `MVP V0.6.6-R7.2.2.1`. |
| Résultat obtenu | La version visible ne correspondait pas à l’archive testée. |
| Résultat attendu | Le titre visible doit afficher `Valoria Vision — V0.6.6-R7.2.3 Imports Fix`. |
| Impact | Confusion de recette et de traçabilité. Non bloquant fonctionnellement. |
| Correctif réalisé | `main.py` définit désormais `APP_VERSION = "V0.6.6-R7.2.3 Imports Fix"` et force le titre de fenêtre après création de `MainWindow`. |
| Vérification attendue | Générer une nouvelle archive installable et confirmer le titre de fenêtre au démarrage. |

---

## R7.2.3-ANO-002 — Identifiant de compte nouvellement créé non masqué

| Champ | Valeur |
|---|---|
| Statut | Corrigé dans la branche de développement — à vérifier sur prochaine archive |
| Gravité | Moyenne côté confidentialité / UX |
| Domaine | Comptes bancaires / confidentialité affichage |
| Détecté par | Recette utilisateur |
| Contexte | Après création d’un compte `SG CC`, le tableau et/ou le volet détail affichaient un identifiant long en clair ou partiellement en clair, contrairement aux comptes existants qui apparaissent sous forme `**** 5541`. |
| Résultat obtenu | Les comptes historiques affichaient un identifiant masqué, mais le nouveau compte affichait une valeur brute ou trop détaillée, par exemple `FR763000300...` dans le tableau et l’identifiant long dans le volet détail. |
| Résultat attendu | Tous les identifiants de comptes doivent être affichés avec la même règle de masquage, quelle que soit leur origine : compte démo, compte existant, compte créé par l’utilisateur. |
| Impact | Incohérence UI et risque de confidentialité visuelle. Non bloquant pour poursuivre le développement correctif. |
| Correctif réalisé | Ajout de `app/r7_2/ui_privacy_patch.py`, activé au démarrage par `main.py`. Le stockage complet en base reste conservé pour les imports, mais l’affichage est masqué dans la liste, les cartes et le volet détail. |
| Vérification attendue | Créer ou afficher un compte avec identifiant complet et confirmer que l’UI affiche seulement `**** 1234` ou équivalent. |

---

## Décision de recette

La R7.2.3 installable a permis de vérifier le démarrage et de révéler des anomalies utiles, mais elle ne constitue pas encore une version de recette complète.

Décision : poursuivre le développement correctif avant de dérouler une recette exhaustive.

Priorité de développement :

1. finaliser les correctifs Imports / Transactions ;
2. corriger les incohérences visibles déjà détectées ;
3. produire une nouvelle archive installable ;
4. recetter ensuite sur un périmètre stabilisé.
