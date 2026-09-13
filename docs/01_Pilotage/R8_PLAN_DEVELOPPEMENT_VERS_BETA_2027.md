# Valoria Vision — Plan exhaustif de développement vers la bêta Standard

**Référence :** VV-PLAN-BETA-2027  
**Version :** 1.1  
**Date de référence :** 7 septembre 2026  
**Cible de publication :** 30 avril 2027  
**Statut :** document de pilotage validé — référentiel de pilotage  
**Dépôt :** `Mnichow36/ValoriaVision`

---

## 1. Objet du document

Ce document fixe le plan de continuité du développement de Valoria Vision jusqu’à l’ouverture de la bêta privée Standard.

Il constitue le référentiel commun pour :

- définir ce qui doit réellement être livré avant la bêta ;
- distinguer le socle Standard des fonctions Premium ;
- ordonner les travaux selon leurs dépendances ;
- fixer les jalons et critères de sortie ;
- calculer une date cible crédible ;
- alimenter correctement le compteur publié sur le site ;
- éviter que des Pull Requests, doublons ou fonctions Premium non planifiées faussent l’avancement ;
- garantir qu’aucune fonction visible ne soit livrée sans développement suffisant et sans recette.

Le plan doit être mis à jour dès qu’un changement de périmètre, une anomalie bloquante ou une dérive de charge modifie la trajectoire.

---

## 2. Décision de planification

### 2.1 Date cible

La date de référence retenue pour une bêta Standard complète est le :

> **vendredi 30 avril 2027**

Le 27 février 2027 correspondait à un calcul antérieur qui ne prenait pas correctement en compte :

- la refonte graphique globale ;
- la finalisation et la recette de Patrimoine ;
- le développement du socle Investissements Standard ;
- les rapports mensuels simples Standard ;
- le socle multidevise ;
- la recette transversale finale.

Cette ancienne date ne doit plus être utilisée comme engagement public.

### 2.2 Niveau de confiance

La cible du 30 avril 2027 est atteignable si les règles suivantes sont respectées :

1. gel du périmètre Standard au plus tard le 18 décembre 2026 ;
2. aucune fonctionnalité Premium avancée dans le chemin critique ;
3. un seul lot fonctionnel principal en cours à la fois ;
4. validation technique et fonctionnelle de chaque lot avant le suivant ;
5. création immédiate d’une issue pour toute anomalie découverte ;
6. absence de bug P0 ouvert au moment de la publication ;
7. absence de bug P1 portant sur l’intégrité, les calculs, la sécurité ou la cohérence métier ;
8. maintien d’une marge finale du 19 au 29 avril 2027.

### 2.3 Fenêtre de risque

- **Cible nominale :** 30 avril 2027.
- **Date au plus tôt raisonnable :** 23 avril 2027.
- **Date de repli sans réduction de périmètre :** 14 mai 2027.

Le compteur du site doit afficher la cible nominale, puis être recalculé à partir de la charge restante.

---

## 3. Périmètre de la bêta Standard

La bêta Standard doit contenir des fonctions utilisables, cohérentes et recettées dans les domaines suivants :

- Dashboard ;
- Comptes ;
- Transactions ;
- Imports ;
- Catégorisation et règles automatiques ;
- Prévisionnel ;
- Récurrences et événements ponctuels ;
- Rapprochements ;
- Budgets ;
- Patrimoine ;
- Investissements Standard ;
- Rapports mensuels simples ;
- Paramètres ;
- Sauvegarde et restauration ;
- Sécurité locale ;
- installation, migration et démarrage ;
- socle multidevise ;
- socle technique de distinction Standard/Premium ;
- charte graphique R8 appliquée à l’ensemble des écrans livrés.

Une fonction visible dans la navigation doit être :

- entièrement fonctionnelle et recettée ;
- ou désactivée/masquée proprement ;
- ou explicitement présentée comme « À venir », sans écran vide ni action inopérante.

---

## 4. Matrice Standard et Premium

| Fonction | Standard bêta | Premium ultérieur |
|---|---:|---:|
| Portefeuille investissements | Oui | Oui |
| Allocation actuelle | Oui | Oui |
| Performance de base | Oui | Oui |
| Historique avancé | Non | Oui |
| Allocation cible | Non | Oui |
| Analyse de concentration | Non | Oui |
| Exposition devises/pays | Non | Oui |
| Objectifs d’investissement | Non | Oui |
| Rapports mensuels simples | Oui | Oui |
| Rapports personnalisés | Non | Oui |
| Rapport Patrimoine 360° | Non | Oui |
| Comparaison de scénarios avancés | Non | Oui |
| Rapport scénario PDF | Non | Oui |
| Analyses automatiques | Non | Oui |
| Assistant IA | Non | Oui |

### 4.1 Décision d’intégration Premium

Avant la bêta, seul le **socle de compatibilité Premium** est développé :

- registre central des fonctionnalités ;
- identification de l’édition ;
- feature flags ;
- contrôle de visibilité et d’accès ;
- navigation sans écran vide ;
- migrations et sauvegardes compatibles ;
- architecture extensible ;
- séparation claire entre logique métier et droits d’édition.

Sont reportés après la bêta :

- fonctions avancées Investissements ;
- scénarios personnalisés et comparaisons avancées ;
- rapports Premium ;
- analyses automatiques ;
- assistant IA ;
- paiement, abonnement et activation commerciale distante.

Référence : issue #118.

---

## 5. Principes d’exécution

### 5.1 Ordre obligatoire

1. Stabiliser le modèle et les règles métier.
2. Sécuriser les migrations et la compatibilité des données.
3. Créer le thème et les composants UI communs.
4. Poser le socle multidevise et Standard/Premium.
5. Migrer les écrans par blocs cohérents.
6. Terminer les modules fonctionnellement incomplets.
7. Recetter chaque module.
8. Exécuter la recette transversale.
9. Produire et vérifier le package bêta.
10. Publier uniquement après décision GO.

### 5.2 Règle de non-régression

Une refonte graphique ne doit jamais modifier silencieusement :

- les calculs ;
- les données ;
- les statuts ;
- les relations entre objets ;
- les règles de sauvegarde ;
- les règles de sécurité ;
- la disponibilité d’une fonction.

### 5.3 Règle de traçabilité

Toute correction doit être liée à :

- une issue GitHub ;
- une branche ;
- une Pull Request ;
- des tests ;
- une version ou un commit de recette ;
- une décision de validation.

### 5.4 Données personnelles

Ne doivent jamais être versionnés :

- base SQLite personnelle ;
- relevé bancaire réel ;
- identifiants de comptes ;
- IBAN ;
- transactions réelles ;
- valorisations patrimoniales personnelles ;
- portefeuille d’investissement réel ;
- mots de passe, clés ou secrets ;
- captures contenant des données identifiantes.

Les tests utilisent des fixtures synthétiques ou anonymisées.

---

## 6. Planning de référence

| Lot | Période | Charge indicative | Résultat attendu |
|---|---|---:|---|
| L0 — Gouvernance et branches | 07/09–18/09/2026 | 5 j | PR documentaires et techniques remises en ordre |
| L1 — Rapprochements métier | 21/09–16/10/2026 | 20 j | Modèle, moteur, persistance, déclencheurs et migrations stabilisés |
| L2 — Socle UI et éditions | 19/10–06/11/2026 | 15 j | Thème R8, composants communs et feature flags |
| L3 — Socle multidevise | 09/11–20/11/2026 | 10 j | Devises, taux datés, conversions et migration |
| L4 — Dashboard | 23/11–04/12/2026 | 10 j | Écran pilote conforme à la charte |
| L5 — Transactions et Imports | 07/12–18/12/2026 | 10 j | Chaîne import/transactions conforme et stable |
| Marge de fin d’année | 21/12/2026–03/01/2027 | — | Corrections, documentation, aucune livraison critique |
| L6 — Comptes | 04/01–15/01/2027 | 10 j | Gestion et cycle de vie des comptes validés |
| L7 — Prévisionnel | 18/01–29/01/2027 | 10 j | Courbes, récurrences, scénarios standards et UI validés |
| L8 — Rapprochements UI/E2E | 01/02–12/02/2027 | 10 j | Écran R8 et scénarios E2E principaux validés |
| L9 — Budgets, Paramètres | 15/02–26/02/2027 | 10 j | Écrans conformes, fonctions existantes préservées |
| L10 — Patrimoine | 01/03–19/03/2027 | 15 j | Fonctions, historique, relations, UI et recette terminés |
| L11 — Investissements Standard | 22/03–09/04/2027 | 15 j | Portefeuille, allocation et performance de base validés |
| L12 — Rapports Standard | 12/04–16/04/2027 | 5 j | Rapport mensuel simple développé et recetté |
| L13 — Recette générale | 19/04–23/04/2027 | 5 j | P0 validés, cohérence intermodules démontrée |
| L14 — Stabilisation et package | 26/04–29/04/2027 | 4 j | Release candidate installable et réversible |
| Publication | 30/04/2027 | — | Ouverture de la bêta privée |

La charge indicative sert au pilotage. Elle doit être remplacée par la charge restante réelle à chaque revue hebdomadaire.

---

## 7. Détail des lots

### L0 — Gouvernance, documentation et branches

#### Objectifs

- valider les documents de fondation R8 ;
- remettre à plat les PR empilées ;
- supprimer les doublons du pilotage ;
- définir l’ordre de fusion ;
- identifier le commit de référence ;
- garantir que seules les issues alimentent le compteur.

#### Références

- PR #92 : fondations fonctionnelles ;
- PR #93 : schéma et migration ;
- PR #94 : moteur/scoring ;
- PR #97 : persistance/réévaluation ;
- PR #95 : doublon fermé, à exclure.

#### Sortie

- documentation relue ;
- branches cohérentes ;
- CI active ;
- aucune PR comptée comme une issue du projet.

---

### L1 — Rapprochements métier

#### Objectifs

- séparer Transaction, Prévision, Proposition et Rapprochement ;
- finaliser la migration non destructive ;
- brancher la qualification aux imports et créations manuelles ;
- réévaluer après modification ;
- sécuriser les annulations ;
- garantir l’intégrité et l’audit ;
- préparer 1↔1, 1↔N, N↔1 et N↔N.

#### Issues principales

- #57 à #61 ;
- #82 ;
- #98 — qualification automatique ;
- #99 — réévaluation ;
- #100 — migration et retour arrière ;
- #101 — E2E et volumétrie;
- #146 — P0 persistance de la base utilisateur après redémarrage, cible corrective R8 TEST12.

#### Priorité de recette au 13/09/2026

- la recette R8 est suspendue au test C20 après constat de la réinitialisation de la base au redémarrage ;
- l’issue #146 est P0 et doit être corrigée dans R8 TEST12 avant reprise ;
- TEST12 doit rester dans la lignée de TEST11, descendante de la référence gelée `v0.6.6-r8-test.9` ;
- la cible bêta du 30/04/2027 reste inchangée tant que cette correction est absorbée par L1.

#### Gate L1

- la base utilisateur, le mot de passe maître et les paramètres persistent après fermeture et relance du package Windows ;
- les données de démonstration ne sont injectées qu’à l’initialisation volontaire d’une nouvelle base ;
- migration réussie et idempotente ;
- mêmes compte et sens obligatoires ;
- Sans prévision, À vérifier et Auto déterministes ;
- aucune transaction source altérée ;
- aucune proposition ou relation orpheline ;
- tests P0 verts.

---

### L2 — Charte, composants et socle Standard/Premium

#### Objectifs

- appliquer la charte R8 de manière centralisée ;
- éviter une refonte indépendante par écran ;
- intégrer le registre des fonctions Standard/Premium ;
- garantir des feature flags cohérents.

#### Issues

- #107 — thème et composants communs ;
- #118 — éditions et feature flags ;
- #35 — navigation et icônes, déjà traitée mais à contrôler.

#### Composants attendus

- AppSidebar ;
- ModuleHeader ;
- KpiCard ;
- VVTable ;
- VVChartPanel ;
- StatusBadge ;
- ActionBar ;
- DetailDrawer/Dialog ;
- EmptyState ;
- FilterBar.

#### Gate L2

- palette et typographie centralisées ;
- mêmes statuts et couleurs partout ;
- navigation cohérente ;
- aucune fonction Premium accessible par erreur ;
- écrans utilisables en 1366 × 768.

---

### L3 — Multidevise

#### Objectifs Standard

- devise de référence EUR par défaut ;
- code ISO 4217 par objet concerné ;
- taux manuel daté ;
- conservation du taux utilisé ;
- montant d’origine non écrasé ;
- consolidation dans une devise commune ;
- migration des données existantes.

#### Issue

- #117.

#### Hors périmètre avant bêta

- taux automatiques ;
- exposition par devise/pays ;
- effet de change avancé ;
- scénarios de change ;
- rapports multidevises avancés.

#### Gate L3

- aucune double conversion ;
- historique reproductible ;
- comportement explicite en cas de taux manquant ;
- sauvegarde et restauration validées.

---

### L4 — Dashboard

#### Issue principale

- #105.

#### Issues liées

- #78 — prénom codé en dur ;
- #19 — performances graphiques.

#### Gate L4

- KPI réconciliables avec les modules sources ;
- aucune donnée personnelle codée en dur ;
- graphiques et statuts conformes à la charte ;
- affichage et rafraîchissement acceptables.

---

### L5 — Transactions et Imports

#### Issue principale

- #103.

#### Issues liées

- #54 — filtres ;
- #86 — sélection ;
- anomalies d’import encore ouvertes ;
- #98 — déclenchement de la qualification après création.

#### Gate L5

- import, contrôle du compte et détection des doublons validés ;
- transactions manuelles et importées traitées de la même manière ;
- actions groupées fiables ;
- aucun identifiant sensible exposé ;
- aucune donnée personnelle dans les fixtures.

---

### L6 — Comptes

#### Issue principale

- #39.

#### Sous-issues

- #40 à #44 ;
- #85 lorsque toujours applicable.

#### Gate L6

- création, modification et archivage ;
- suppression physique uniquement si le compte est vide ;
- préservation des dépendances ;
- identifiants masqués ;
- devises compatibles ;
- mise à jour immédiate des modules consommateurs.

---

### L7 — Prévisionnel

#### Issue principale

- #104.

#### Issues liées

- #7 — popups ;
- #64 — scénarios standards ;
- récurrences et événements ponctuels encore ouverts.

#### Gate L7

- scénarios Prudent/Réaliste/Optimiste fonctionnels ;
- courbes et indicateurs réconciliés ;
- récurrences et événements ponctuels fiables ;
- infobulles complètes ;
- calculs multidevises cohérents lorsque nécessaires.

---

### L8 — Rapprochements UI et E2E

#### Issues

- #82 ;
- #101 ;
- #57 à #61.

#### Gate L8

- transactions, prévisions et proposition présentées ensemble ;
- score expliqué ;
- KPI égaux aux populations ;
- annulation et réactivation ;
- filtres sans effet métier ;
- prévisionnel sans double comptage ;
- tests 10, 100, 500, 501, 1 000 et 10 000 éléments.

---

### L9 — Budgets et Paramètres

#### Issues

- #102 — Budgets ;
- #106 — Paramètres ;
- #29 et #31 — nettoyage Paramètres ;
- autres anomalies ouvertes du périmètre.

#### Gate L9

- Budgets : prévu, réalisé et écart cohérents ;
- actions Nouveau/Ajuster distinctes ;
- Paramètres sans laboratoire technique visible ;
- sauvegarde et sécurité accessibles ;
- aucune fonction existante perdue.

---

### L10 — Patrimoine

#### Issues

- #27 — synthèse ;
- #83 — historique ;
- #84 — rattachement aux comptes ;
- #108 — UI ;
- #109 — recette ;
- #19 — performances.

#### Périmètre

- actifs et passifs ;
- valorisations ;
- crédits associés ;
- calcul Actifs − Passifs = Net ;
- liquidités ;
- familles et poids ;
- historique explicatif ;
- intégration Comptes et Dashboard ;
- sauvegarde/restauration ;
- multidevise ;
- aucune recommandation financière personnalisée.

#### Gate L10

- calculs réconciliés ;
- historique conservé ;
- cycles de vie validés ;
- aucune donnée orpheline ;
- aucune incohérence entre KPI, graphique, tableau et volet ;
- décision GO/NO GO #109.

---

### L11 — Investissements Standard

#### Issues

- #114 — développement ;
- #110 — recette ;
- #117 — dépendance multidevise ;
- #84/#109 — intégration Patrimoine.

#### Périmètre Standard

- portefeuille ;
- allocation actuelle ;
- performance de base ;
- positions et opérations nécessaires ;
- intégration Patrimoine ;
- fonctionnement local ;
- interface R8.

#### Gate L11

- valeur investie, valeur actuelle et performance réconciliées ;
- allocation totale cohérente ;
- cycle de vie sécurisé ;
- sauvegarde/restauration ;
- absence de double comptage ;
- fonctions Premium masquées ;
- décision GO/NO GO #110.

---

### L12 — Rapports mensuels simples

#### Issue

- #113.

#### Périmètre Standard

- rapport mensuel simple ;
- période et date de génération ;
- revenus et dépenses ;
- principales catégories ;
- synthèses cohérentes avec les modules sources ;
- export uniquement s’il est fiable et sécurisé.

#### Gate L12

- totaux réconciliés ;
- états vides gérés ;
- données sensibles protégées ;
- fonctions Premium masquées ;
- décision GO/NO GO.

---

### L13 — Recette générale

#### Périmètre

- installation ;
- première ouverture ;
- migration ;
- comptes ;
- imports ;
- transactions ;
- catégorisation ;
- prévisionnel ;
- rapprochements ;
- budgets ;
- patrimoine ;
- investissements Standard ;
- rapports Standard ;
- paramètres ;
- sécurité ;
- sauvegarde/restauration ;
- multidevise ;
- droits Standard/Premium ;
- performances et volumétrie.

#### Gate L13

- 100 % des tests P0 verts ;
- aucun bug P0 ouvert ;
- aucun P1 d’intégrité/cohérence/sécurité ouvert ;
- toutes les données affichées réconciliables ;
- aucune fonction incomplète visible ;
- documentation et version testée identifiées.

---

### L14 — Stabilisation et publication

#### Travaux

- corriger uniquement les anomalies bloquant la sortie ;
- produire le package ;
- tester installation et mise à jour ;
- tester sauvegarde avant migration et retour arrière ;
- vérifier le coffre local et le verrouillage ;
- préparer les notes de version ;
- figer le commit ;
- exécuter le dernier smoke test ;
- prendre la décision GO/NO GO.

#### Règle

Aucune nouvelle fonctionnalité ne peut entrer dans L14.

---

## 8. Backlog Premium après la bêta

### 8.1 Scénarios avancés

- #21 — impacts des événements ;
- #22 — durée ;
- #63 — scénarios personnalisés ;
- #112 — recette Premium.

### 8.2 Investissements avancés

- #115 — historique avancé, allocation cible, concentration, devises/pays et objectifs.

### 8.3 Rapports Premium

- #111 — rapports personnalisés, Patrimoine 360°, rapports scénarios et exports avancés.

### 8.4 Analyses et IA

- #116 — analyses automatiques et assistant IA.

### 8.5 Ordre Premium recommandé

1. Scénarios avancés, car une partie du socle existe déjà.
2. Investissements avancés, sur le socle Standard stabilisé.
3. Rapports Premium, après Investissements et Scénarios.
4. Analyses automatiques.
5. Assistant IA, uniquement sur des données et explications stabilisées.

Ces issues doivent porter la version cible **Non planifiée** tant qu’une release Premium n’est pas décidée.

---

## 9. Pilotage GitHub Project

### 9.1 Champs obligatoires

Chaque issue du périmètre doit renseigner :

- Status ;
- Type ;
- Module principal ;
- Version cible ;
- Priorité ;
- Validation ;
- Charge estimée en jours ;
- Charge restante en jours ;
- Date de début cible ;
- Date de fin cible ;
- Lot ;
- Dépend de / Bloqué par.

### 9.2 Statuts

- **Backlog :** identifié mais non immédiatement exécutable ;
- **Prête à développer :** critères et dépendances suffisamment définis ;
- **Livrée :** développement terminé et intégré ;
- la validation doit rester distincte de la livraison technique.

Une issue ne doit pas être considérée terminée uniquement parce qu’une PR existe.

### 9.3 Règles du compteur

Le compteur du site doit :

- compter uniquement les objets GitHub de type Issue ;
- exclure les Pull Requests ;
- exclure les doublons ;
- inclure uniquement `Version cible = V1.0 — Bêta privée` ;
- exclure les issues `Non planifiée` ;
- ne pas compter simultanément une Epic et toutes ses sous-issues sans pondération ;
- utiliser la charge restante plutôt qu’un simple nombre d’issues ;
- prendre en compte la validation, pas seulement le statut Livrée ;
- afficher la date du dernier recalcul.

### 9.4 Formule recommandée

```text
Progression = 1 - (somme des charges restantes / somme des charges initiales)
```

Une issue livrée mais non recettée conserve une charge résiduelle de validation.

---

## 10. Gouvernance hebdomadaire

Chaque semaine :

1. vérifier les issues terminées ;
2. mettre à jour la charge restante ;
3. contrôler les dépendances ;
4. analyser les échecs CI ;
5. vérifier les anomalies de recette ;
6. recalculer la date cible ;
7. documenter toute dérive supérieure à cinq jours ouvrés ;
8. décider si un élément doit être corrigé, reporté ou masqué.

### Revue de jalon

À la fin de chaque lot :

- démonstration ;
- tests automatisés ;
- recette ciblée ;
- décision accepté/refusé ;
- mise à jour du projet ;
- mise à jour du compteur.

---

## 11. Critères de GO bêta

La bêta est autorisée uniquement si :

- tous les lots Standard sont terminés ;
- la matrice Standard annoncée est respectée ;
- aucun P0 n’est ouvert ;
- aucun P1 d’intégrité, de calcul, de sécurité ou de perte de données n’est ouvert ;
- les migrations sont réversibles par restauration de sauvegarde ;
- les données personnelles restent locales et protégées ;
- le socle multidevise est cohérent ;
- les fonctions Premium sont correctement masquées ou identifiées ;
- chaque module visible possède une recette récente ;
- le package d’installation est validé ;
- le commit et la version de référence sont figés ;
- une décision GO explicite est consignée.

---

## 12. Motifs de NO GO

La publication est interdite si l’un des cas suivants subsiste :

- perte ou corruption de données ;
- double comptage ;
- solde ou patrimoine non réconciliable ;
- rapprochement incohérent ou irréversible ;
- conversion de devise non reproductible ;
- sauvegarde ou restauration non fiable ;
- fonction Premium accessible sans contrôle ;
- fonction visible mais non fonctionnelle ;
- migration non testée ;
- incohérence majeure KPI/liste ;
- donnée personnelle présente dans un livrable public ;
- tests P0 rouges.

---

## 13. Gestion des modifications du plan

Toute évolution doit indiquer :

- la date ;
- l’auteur ;
- la raison ;
- les issues concernées ;
- l’impact sur la charge ;
- l’impact sur la date cible ;
- la décision prise.

### Historique

| Version | Date | Modification |
|---|---|---|
| 1.0 | 07/09/2026 | Création, validation du plan exhaustif et fixation de la cible au 30/04/2027 |
| 1.1 | 13/09/2026 | Ajout du P0 #146 : persistance globale au redémarrage, TEST12 prioritaire dans L1, cible bêta provisoirement inchangée |

---

## 14. Synthèse décisionnelle

- La bêta visée est une **bêta Standard complète**, pas une démonstration partielle.
- Investissements Standard et Rapports mensuels simples sont inclus avant la bêta.
- Le socle multidevise est inclus avant la bêta.
- L’architecture Standard/Premium est intégrée avant la bêta.
- Les fonctions Premium avancées sont développées après la bêta.
- La charte graphique R8 s’applique à tous les écrans livrés.
- La date nominale est le **30 avril 2027**.
- Le compteur public doit être recalculé à partir de la charge restante réelle.
