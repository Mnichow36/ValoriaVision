# Valoria Vision — R8 Rapprochements
## Spécification fonctionnelle de référence

**Statut :** proposition de référence pour refonte
**Dépôt :** Mnichow36/ValoriaVision
**Branche de préparation :** docs/r8-rapprochements-fondations
**Référence précédente :** R7.2 — Écran cible Rapprochements et qualification automatique

## 1. Objectif

Le module Rapprochements doit qualifier automatiquement toute transaction réelle et permettre de relier de manière explicable, traçable et réversible les transactions réelles aux occurrences prévisionnelles.

Le module fonctionne selon un principe de **contrôle par exception** : les cas certains sont traités automatiquement, les cas ambigus sont proposés à l'utilisateur, et les transactions sans prévision connue sont qualifiées sans imposer un traitement manuel.

## 2. Objets métier

### 2.1 Transaction réelle
Opération financière effectivement constatée, issue :
- d'un import bancaire ;
- d'une saisie manuelle.

Une transaction réelle conserve ses attributs propres : compte, date, montant, sens, libellé, catégorie, source et références externes éventuelles.

### 2.2 Occurrence prévisionnelle
Instance datée d'une prévision ou d'une récurrence.

Elle possède son propre cycle de vie et ne doit pas porter à elle seule l'état complet d'un rapprochement.

### 2.3 Proposition de rapprochement
Résultat non final d'une analyse du moteur entre un ou plusieurs éléments réels et un ou plusieurs éléments prévisionnels.

Une proposition contient au minimum :
- ses membres ;
- le score global ;
- les scores/critères détaillés ;
- le niveau de confiance ;
- les écarts de date et de montant ;
- la date de calcul ;
- les règles utilisées.

### 2.4 Rapprochement
Décision finalisée reliant un groupe de transactions réelles à un groupe d'occurrences prévisionnelles.

Un rapprochement peut être :
- automatique ;
- confirmé manuellement.

Il doit être annulable sans modifier les données financières d'origine.

## 3. Invariants métier

### RME-R8-001 — Intégrité des transactions
Un rapprochement ne doit jamais modifier ni supprimer silencieusement le montant, la date, le compte, le sens ou le libellé d'une transaction réelle.

### RME-R8-002 — Qualification systématique
Toute transaction réelle nouvellement intégrée, importée ou saisie manuellement, doit être soumise au moteur.

### RME-R8-003 — Même compte
Par défaut, un rapprochement automatique entre comptes différents est interdit.

### RME-R8-004 — Même sens
Un débit ne peut jamais être rapproché automatiquement d'un crédit, et inversement.

### RME-R8-005 — Ambiguïté
Une forte note absolue ne suffit pas à autoriser un rapprochement automatique si plusieurs candidats proches existent.

### RME-R8-006 — Réversibilité
Toute décision de rapprochement finalisée doit pouvoir être annulée lorsque les données sources existent toujours.

### RME-R8-007 — Explicabilité
Tout score ou niveau de confiance affiché doit être accompagné des critères ayant contribué à la décision.

### RME-R8-008 — Audit
Les transitions importantes doivent être historisées de façon à reconstruire le parcours métier.

### RME-R8-009 — Filtres sans effet métier
Les filtres d'écran ne modifient jamais le jeu de données sous-jacent ni les décisions du moteur.

### RME-R8-010 — Réévaluation
Une qualification « Réalisée sans prévision » ou une proposition non finalisée peut être recalculée si le contexte prévisionnel ou les paramètres du moteur changent.

## 4. Résultats possibles de qualification

### 4.1 Rapprochée automatiquement
Conditions minimales :
- critères obligatoires satisfaits ;
- score supérieur ou égal au seuil automatique ;
- absence d'ambiguïté significative.

### 4.2 À vérifier
Cas typiques :
- score intermédiaire ;
- plusieurs candidats crédibles ;
- critère non bloquant incertain ;
- regroupement nécessitant validation.

### 4.3 Réalisée sans prévision
Aucun candidat plausible n'existe au moment de l'analyse.

Cette qualification :
- est persistée ;
- n'impose aucune action manuelle ;
- reste consultable ;
- reste réévaluable.

## 5. Critères de scoring

Le moteur doit pouvoir utiliser au minimum :
- compte bancaire ;
- sens débit/crédit ;
- date ;
- montant absolu ;
- montant en pourcentage ;
- libellé ;
- catégorie ;
- bénéficiaire/émetteur si disponible ;
- référence bancaire ou identifiant externe si disponible ;
- historique de rapprochements similaires si activé.

Les règles et pondérations doivent être séparées du code de présentation.

## 6. Paramétrage

Les valeurs par défaut doivent être versionnées.

Au minimum :
- seuil de rapprochement automatique ;
- seuil de proposition ;
- écart minimal entre premier et second candidat pour autoriser l'automatique ;
- tolérance de date ;
- tolérance de montant absolue ;
- tolérance de montant relative ;
- critères obligatoires ;
- poids des critères.

Les réglages propres à l'utilisateur restent dans les données locales et ne sont pas versionnés.

## 7. Gestion de l'ambiguïté

Le moteur compare le meilleur candidat au suivant.

Exemple :
- candidat A = 95 ;
- candidat B = 94.

Résultat attendu : **À vérifier**, même si 95 dépasse le seuil automatique.

Le seuil d'écart minimal doit être paramétrable.

## 8. Cas 1↔1 et N↔N

Le modèle doit être compatible avec :
- 1 transaction ↔ 1 occurrence ;
- 1 transaction ↔ N occurrences ;
- N transactions ↔ 1 occurrence ;
- N transactions ↔ N occurrences.

Pour un groupe, le système calcule :
- total réel ;
- total prévu ;
- écart global ;
- membres ;
- score ;
- justification.

## 9. Cycle des occurrences

Une occurrence peut notamment être :
- planned ;
- overdue ;
- ignored ;
- cancelled.

Les états de rapprochement ne doivent plus être confondus avec les états propres de l'occurrence.

Une occurrence ignorée doit pouvoir être remise à traiter.
Une occurrence active doit pouvoir être annulée explicitement.
Une occurrence annulée reste dans l'historique.

## 10. Cycle des propositions et rapprochements

Une proposition peut être :
- proposed ;
- rejected ;
- expired ;
- converted.

Un rapprochement peut être :
- automatic ;
- confirmed ;
- cancelled.

L'annulation d'un rapprochement :
- libère ses membres ;
- ne supprime aucune donnée source ;
- déclenche une réévaluation si nécessaire ;
- est historisée.

## 11. Déclencheurs de réévaluation

Une réévaluation doit être possible après :
- création d'une transaction ;
- import bancaire ;
- modification d'une transaction ;
- création d'une prévision ;
- création d'une récurrence ;
- modification d'une prévision ;
- changement des paramètres ;
- annulation d'un rapprochement ;
- enrichissement d'une donnée métier.

Les règles précises de réévaluation doivent empêcher les boucles et les décisions silencieuses incohérentes.

## 12. Interface cible

L'écran comprend au minimum :
- KPI de synthèse ;
- Transactions à rapprocher ;
- Prévisions à traiter ;
- panneau Proposition de rapprochement ;
- score et explication ;
- actions Valider / Ignorer / Mode manuel ;
- accès aux détails et à l'historique.

KPI fonctionnels minimaux :
- À vérifier ;
- Prévisions ouvertes ;
- Sans prévision ;
- Rapprochées.

## 13. Cohérence des vues

Lorsqu'un filtre de rapprochement est appliqué, les listes affichées doivent présenter des populations liées et compréhensibles.

Exemple « Rapprochées » :
- seules les transactions membres des rapprochements affichés sont montrées ;
- seules les occurrences membres correspondantes sont montrées.

Un KPI doit toujours être réconciliable avec la population accessible par son filtre.

## 14. Traçabilité utilisateur

La vue détail doit afficher selon le cas :
- données transaction ;
- données occurrence ;
- origine prévisionnelle ;
- score ;
- critères ;
- type de rapprochement ;
- dates de création/confirmation/annulation ;
- motifs d'ignorance ou d'annulation ;
- historique des transitions.

L'identifiant technique reste secondaire.

## 15. Prévisionnel et double comptage

Une occurrence remplacée économiquement par un réalisé rapproché ne doit pas provoquer un double comptage prévu + réalisé.

Le comportement doit être testé pour :
- rapprochement automatique ;
- rapprochement manuel ;
- proposition ;
- annulation ;
- ignorance.

## 16. Modification et suppression des données sources

### Modification d'une transaction rapprochée
Toute modification susceptible d'invalider le rapprochement déclenche une réévaluation ou place le rapprochement dans un état explicitement incohérent à traiter. Un lien devenu impossible ne doit jamais être conservé silencieusement.

### Suppression d'une transaction
Les rapprochements/propositions liés sont annulés ou invalidés proprement avant suppression. Les occurrences retrouvent un état cohérent.

### Suppression d'un import
Même règle pour toutes les transactions du lot.

## 17. Détection de récurrence potentielle

Plusieurs transactions « Sans prévision » similaires peuvent donner lieu à une proposition :
« Dépense / recette récurrente détectée — Créer une récurrence ? »

Aucune récurrence ne doit être créée sans validation utilisateur.

## 18. Critères de validation fonctionnelle

La refonte est considérée conforme lorsque :
- tous les tests P0 du plan de recette sont verts ;
- aucune transaction réelle n'est altérée par le rapprochement ;
- import et saisie manuelle déclenchent la même qualification ;
- les ambiguïtés ne sont jamais masquées par un rapprochement automatique ;
- « Sans prévision » est une qualification métier persistée et réévaluable ;
- chaque décision est explicable et auditée ;
- les filtres n'altèrent jamais le dataset ;
- les vues et KPI sont réconciliables ;
- le modèle supporte les groupes N↔N ;
- l'annulation restaure un état cohérent ;
- le prévisionnel ne double pas prévu et réalisé.
