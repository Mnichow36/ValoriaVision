# Valoria Vision — Matrice de reprise de recette R7 / R7.2

**Date de référence :** 04/09/2026  
**Version examinée :** V0.6.6-R7.2.4 — release de recette #31  
**Décision :** **NON CONFORME — NE PAS UTILISER COMME RÉFÉRENCE**  
**Issue maîtresse :** [#52 — Recette corrective V0.6.6-R7.2](https://github.com/Mnichow36/ValoriaVision/issues/52)

## 1. Objet et règle de reprise

La recette est reprise à partir des exigences et critères d'acceptation enregistrés dans les issues GitHub, et non à partir des seuls écrans récemment modifiés. Chaque fonctionnalité précédemment déclarée terminée doit être rejouée sur une même version candidate afin d'éviter les régressions croisées.

Aucune nouvelle archive installable ne doit être considérée comme candidate bêta tant que les portes de validation ci-dessous ne sont pas franchies. La release #31 reste disponible uniquement pour traçabilité ; elle est invalidée par deux régressions confirmées : [#2](https://github.com/Mnichow36/ValoriaVision/issues/2) et [#78](https://github.com/Mnichow36/ValoriaVision/issues/78).

### États utilisés

| État | Signification |
|---|---|
| **Non conforme** | Le défaut est observé et reproductible sur la release #31. |
| **À rejouer** | L'issue a déjà été déclarée terminée, mais sa preuve doit être renouvelée sur la prochaine version candidate. |
| **Conforme prouvé** | Test automatisé réussi et preuve manuelle datée sur la même version candidate. |
| **Non applicable** | Élément explicitement exclu du périmètre bêta ; il ne compte pas dans la progression. |

## 2. Régressions bloquantes constatées

| Issue | Priorité | Module | Critère à vérifier | Preuve attendue | État actuel | Décision |
|---|---:|---|---|---|---|---|
| [#2 — Modification d'une transaction](https://github.com/Mnichow36/ValoriaVision/issues/2) | P0 | Transactions | Tous les champs principaux sont modifiables ; le sens débit/crédit et le signe du montant sont conservés après plusieurs modifications. Tester une transaction manuelle, importée et de démonstration. | Tests automatisés sur les trois origines + captures avant/après + contrôle en base. | **Non conforme** | Issue rouverte ; bloque toute nouvelle release. |
| [#78 — Prénom codé en dur dans le Dashboard](https://github.com/Mnichow36/ValoriaVision/issues/78) | P1 | Dashboard | Le titre reste neutre (`Bonjour`) tant qu'aucun profil utilisateur n'est réellement disponible ; aucune donnée nominative de démonstration ne doit apparaître. | Test d'interface + recherche globale du prénom dans le code et les données livrées. | **Non conforme** | Issue rouverte ; correction obligatoire avant reprise globale. |

## 3. Socle R7 à rejouer intégralement

Les issues ci-dessous ont été fermées par le passé. Elles ne sont pas réputées conformes sur la prochaine version candidate sans nouvelle preuve.

| Issue | Priorité | Module | Test de recette fondé sur l'issue | Preuve automatisée minimale | Preuve manuelle minimale | État |
|---|---:|---|---|---|---|---|
| [#4 — Sélection des fichiers CSV](https://github.com/Mnichow36/ValoriaVision/issues/4) | P0 | Imports | Choisir un CSV, annuler le sélecteur, puis importer un fichier valide et un fichier invalide sans blocage. | Tests du parseur et des erreurs d'entrée. | Capture du parcours et résultat d'import. | À rejouer |
| [#8 — Événement prévisionnel ponctuel](https://github.com/Mnichow36/ValoriaVision/issues/8) | P0 | Prévisionnel | Créer, modifier et supprimer une occurrence unique ; vérifier dates, montant, compte et catégorie. | Tests CRUD et persistance. | Contrôle après redémarrage. | À rejouer |
| [#11 — Application manuelle des règles](https://github.com/Mnichow36/ValoriaVision/issues/11) | P0 | Transactions | Exécuter une règle de catégorisation, vérifier les opérations éligibles et l'absence de modification hors cible. | Tests de sélection et d'application des règles. | Comparatif avant/après. | À rejouer |
| [#12 — Création d'une récurrence](https://github.com/Mnichow36/ValoriaVision/issues/12) | P0 | Prévisionnel | Créer une récurrence et vérifier ses occurrences, sa fréquence, ses dates limites et sa persistance. | Tests de génération des occurrences. | Contrôle de la liste après redémarrage. | À rejouer |
| [#15 — Transactions manuelles dans les rapprochements](https://github.com/Mnichow36/ValoriaVision/issues/15) | P0 | Rapprochements | Une transaction manuelle éligible doit apparaître et pouvoir être rapprochée sans différence de traitement avec un import. | Test d'éligibilité par origine. | Rapprochement manuel complet. | À rejouer |
| [#17 — Retards et compteurs](https://github.com/Mnichow36/ValoriaVision/issues/17) | P0 | Prévisionnel / Rapprochements | Marquer les retards ; vérifier statut, compteurs et absence de double comptage. | Tests de transition de statut et agrégats. | Comparaison liste/compteurs. | À rejouer |
| [#23 — Modifier/supprimer un actif](https://github.com/Mnichow36/ValoriaVision/issues/23) | P0 | Patrimoine | Modifier puis supprimer un actif ; vérifier tous les totaux et graphiques dépendants. | Tests CRUD et recalcul. | Captures avant/après. | À rejouer |
| [#24 — Dettes classées comme actifs](https://github.com/Mnichow36/ValoriaVision/issues/24) | P0 | Patrimoine | Une dette reste un passif dans toutes les listes, répartitions et synthèses. | Test de classification. | Contrôle Dashboard et Patrimoine. | À rejouer |
| [#25 — Cohérence des indicateurs patrimoniaux](https://github.com/Mnichow36/ValoriaVision/issues/25) | P0 | Patrimoine / Dashboard | Actifs, passifs et patrimoine net utilisent les mêmes données et la même formule sur tous les écrans. | Tests d'agrégats partagés. | Recalcul manuel sur un jeu connu. | À rejouer |
| [#30 — Sauvegarde chiffrée](https://github.com/Mnichow36/ValoriaVision/issues/30) | P1 | Sécurité / Données | Créer une sauvegarde, vérifier son chiffrement, restaurer dans un environnement propre et comparer les données. | Tests sauvegarde/restauration. | Preuve de restauration complète. | À rejouer |
| [#49 — Éligibilité exhaustive aux rapprochements](https://github.com/Mnichow36/ValoriaVision/issues/49) | P0 | Rapprochements | Toutes les transactions réelles éligibles apparaissent, quelle que soit leur origine, sans doublon ni exclusion silencieuse. | Tests par origine, statut et compte. | Comptage source/liste et exemples ciblés. | À rejouer |

## 4. Lot R7.2 Imports & Rapprochements

| Issue | Priorité | Fonction attendue / critère principal | Preuve requise | État |
|---|---:|---|---|---|
| [#53 — Faux doublons import Société Générale](https://github.com/Mnichow36/ValoriaVision/issues/53) | P0 | Importer 314 opérations et conserver les deux opérations distinctes de **-7,76 € du 15/06/2026**. | Rejouer le fichier réel sur la version finale ; rapport `314 importées`, contrôle des deux lignes et absence de perte. | À rejouer — preuve historique conforme, à renouveler. |
| [#55 — Bouton de gestion des récurrences](https://github.com/Mnichow36/ValoriaVision/issues/55) | P1 | Le bouton ouvre le bon parcours et permet la gestion effective des récurrences. | Test de navigation + création/modification réelle. | À rejouer |
| [#56 — Transactions hors import bancaire](https://github.com/Mnichow36/ValoriaVision/issues/56) | P0 | Les transactions manuelles et de démonstration éligibles sont présentes dans Rapprochements. | Tests par origine + contrôle visuel des listes. | À rejouer |
| [#82 — Pré-rapprochement cible bêta](https://github.com/Mnichow36/ValoriaVision/issues/82) | P1 | Des propositions sont calculées automatiquement **avant** toute sélection manuelle ; la sélection sert à examiner/valider/rejeter, pas à déclencher le calcul. | Tests du moteur de proposition et classement des scores + scénario manuel sans présélection. | À développer / Non conforme |
| [#57 — Règles et seuils automatiques](https://github.com/Mnichow36/ValoriaVision/issues/57) | P1 | Le moteur applique des règles explicables, des seuils stables et ne rapproche pas automatiquement les cas ambigus. | Tests des seuils, cas limites et justification du score. | À développer / À recetter |
| [#58 — Restaurer une occurrence ignorée](https://github.com/Mnichow36/ValoriaVision/issues/58) | P1 | Une occurrence ignorée peut être retrouvée et restaurée sans perte d'historique. | Test complet ignorer/restaurer. | À développer / À recetter |
| [#59 — Annuler une occurrence](https://github.com/Mnichow36/ValoriaVision/issues/59) | P1 | L'annulation change le statut et les compteurs sans supprimer l'historique. | Test de transition et cohérence des totaux. | À développer / À recetter |
| [#60 — Information et historique](https://github.com/Mnichow36/ValoriaVision/issues/60) | P1 | Chaque rapprochement expose son origine, son statut et son historique compréhensible. | Test de traçabilité des actions. | À développer / À recetter |
| [#61 — Filtres de statut et transactions associées](https://github.com/Mnichow36/ValoriaVision/issues/61) | P1 | Chaque filtre affiche les occurrences et transactions associées cohérentes avec son compteur. | Tests croisés filtres/listes/compteurs. | À développer / À recetter |
| [#54 — Ergonomie des filtres Transactions](https://github.com/Mnichow36/ValoriaVision/issues/54) | P2 | Les filtres restent lisibles, utilisables et sans effet de bord sur le jeu de données. | Test UI multi-résolutions et non-altération des données. | À traiter après les blocants |
| [#52 — Recette corrective R7.2](https://github.com/Mnichow36/ValoriaVision/issues/52) | Recette | Consolide l'ensemble des preuves et interdit la livraison en présence d'une régression bloquante. | Checklist complète, liens vers tests, captures, version et jeu de données. | **Bloquée par #2 et #78** |

## 5. Ordre d'exécution et portes de validation

### Porte 0 — Gel et traçabilité

- Conserver la release #31 uniquement comme preuve de la régression.
- Ne produire aucune nouvelle release à partir d'une correction isolée.
- Sauvegarder le jeu de données de recette et noter précisément sa version.

### Porte 1 — Socle P0

Corriger d'abord #2, puis rejouer Transactions, Imports, Comptes et Patrimoine : #4, #11, #23, #24, #25, #30. La porte échoue au premier écart de données, de signe ou de total.

### Porte 2 — Prévisionnel et récurrences

Rejouer #8, #12, #17 et #55 : création, modification, suppression, génération des occurrences, retards, compteurs et persistance après redémarrage.

### Porte 3 — Cycle de vie Rapprochements

Valider dans cet ordre #49, #53, #56, #82, puis #57 à #61. Le moteur doit proposer automatiquement les correspondances avant intervention de l'utilisateur. Terminer par la recette transversale #52.

### Porte 4 — Non-régression transversale

Valider #78 puis parcourir Dashboard, Comptes, Transactions, Prévisionnel, Rapprochements et Patrimoine. Vérifier navigation, textes, filtres, montants, dates, performances, redémarrage et cohérence des indicateurs.

L'historique patrimonial [#83](https://github.com/Mnichow36/ValoriaVision/issues/83), ciblé V1.0 bêta privée, est traité après la stabilisation R7.2 mais avant la décision finale bêta.

### Porte 5 — Candidate bêta

- Construire une seule archive installable à partir du commit ayant passé toutes les portes.
- Refaire le test Société Générale #53 sur cette archive exacte.
- Installer dans un dossier vierge, démarrer sans erreur et conserver les preuves dans #52.
- Fermer les issues uniquement après rattachement du commit, du test automatisé et de la preuve manuelle.

## 6. Périmètre exclu du calcul bêta

Sont exclus du dénominateur de progression :

- les fonctions **Premium** ;
- le **SEO**, la communication et le contenu marketing ;
- les issues marquées **Non applicable** ou **Not planned** ;
- les doublons, notamment [#81](https://github.com/Mnichow36/ValoriaVision/issues/81), doublon de #78 ;
- les issues purement administratives sans critère fonctionnel testable.

Une exclusion doit rester explicite et justifiée dans GitHub ; elle ne vaut jamais validation fonctionnelle.

## 7. Indicateur de progression bêta pondéré

Le simple ratio `issues fermées / issues totales` est insuffisant : il donne le même poids à une anomalie de signe financier P0 et à une finition ergonomique P2.

Pondération recommandée :

| Niveau | Poids | Condition de comptabilisation |
|---|---:|---|
| P0 — Bloquant données/métier | 5 | Test automatisé et recette manuelle conformes sur la candidate. |
| P1 — Fonction majeure bêta | 3 | Critères d'acceptation et non-régression prouvés. |
| P2 — Ergonomie/finition | 1 | Validation visuelle et fonctionnelle. |

Formule :

`Progression bêta = somme des poids conformes prouvés / somme des poids applicables`

Une seule issue P0 non conforme place en plus l'indicateur global en **BLOQUÉ**, quel que soit le pourcentage. Au 04/09/2026, la progression ne doit donc pas être présentée comme un pourcentage de livraison : elle est **BLOQUÉE par #2**, avec #78 également non conforme.

## 8. Définition de terminé

Une issue fonctionnelle ne peut être déclarée `completed` que si les quatre éléments suivants sont réunis sur la même version candidate :

1. correction identifiée par un commit ;
2. test automatisé ciblé réussi ;
3. recette manuelle fondée sur les critères de l'issue ;
4. preuve datée liée dans GitHub (résultat, capture ou rapport).

La fermeture passée d'une issue n'exonère jamais son rejeu lorsqu'une nouvelle candidate bêta modifie le même module ou un flux transverse.
