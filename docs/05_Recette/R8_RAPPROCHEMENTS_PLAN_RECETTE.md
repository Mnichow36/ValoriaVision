# Valoria Vision — R8 Rapprochements
## Plan de tests et de recette

**Référentiel :** R8_RAPPROCHEMENTS_SPECIFICATION_FONCTIONNELLE.md  
**Machine à états :** R8_RAPPROCHEMENTS_MACHINE_ETATS.md  
**ADR :** ADR_R8_MODELE_RAPPROCHEMENTS.md

## 1. Objectif

Valider de bout en bout la chaîne :

**Prévision / récurrence → occurrence + transaction réelle → qualification → proposition → rapprochement → audit → prévisionnel**

La recette doit vérifier les comportements fonctionnels, l'intégrité des données, la réversibilité, la cohérence des vues et l'absence de double comptage.

## 2. Niveaux de test

### A — Unitaires
Scoring, recherche de candidats, ambiguïté, transitions et règles de qualification.

### B — Intégration
Base SQLite temporaire, migrations, relations, annulations, suppressions, réévaluation.

### C — Chaîne métier
Import/saisie manuelle → moteur → prévisionnel.

### D — Recette UI
KPI, listes, panneau de proposition, détails, historique, actions.

### E — Non-régression et volumétrie
Transactions, imports, catégorisation, prévisionnel, dashboard, navigation et limites.

## 3. Jeu de données de référence

Versionner des fixtures couvrant au minimum :
- D01 match exact unique ;
- D02 date +1 jour ;
- D03 petit écart montant ;
- D04 date à la limite ;
- D05 date hors tolérance ;
- D06 compte différent ;
- D07 sens opposé ;
- D08 libellé très différent ;
- D09 deux candidats presque équivalents ;
- D10 aucune prévision ;
- D11 transaction manuelle ;
- D12 occurrence en retard ;
- D13 1→N ;
- D14 N→1 ;
- D15 N→N.

## 4. Tests P0 — moteur

### REC-MOT-001 — Même compte obligatoire
Deux éléments sur des comptes différents ne peuvent pas être rapprochés automatiquement.

### REC-MOT-002 — Même sens obligatoire
Débit ↔ crédit interdit, même avec montant/date/libellé identiques.

### REC-MOT-003 — Match exact unique
Score élevé, explication complète, auto si aucune ambiguïté.

### REC-MOT-004 — Tolérance date
Tester J, J±1, J±3, limite, limite+1.

### REC-MOT-005 — Tolérance montant
Tester exact, seuil absolu, seuil relatif, juste sous/au-dessus.

### REC-MOT-006 — Libellé
Tester casse, accents, tirets, enrichissement bancaire, libellé sans rapport.

### REC-MOT-007 — Catégorie
L'absence de catégorie ne doit pas éliminer abusivement un candidat.

### REC-MOT-008 — Ambiguïté forte
A=95, B=94 → À vérifier, jamais auto.

### REC-MOT-009 — Aucun candidat
La transaction devient « Réalisée sans prévision ».

### REC-MOT-010 — Paramètres modifiés
Changer seuils/tolérances et vérifier le résultat après recalcul.

## 5. Qualification automatique

### REC-QLF-001 — Import bancaire
Toute transaction importée est qualifiée immédiatement.

### REC-QLF-002 — Saisie manuelle
Toute transaction manuelle suit la même chaîne.

### REC-QLF-003 — Modification transaction
Date, montant, compte, sens, libellé ou catégorie peuvent déclencher une réévaluation.

### REC-QLF-004 — Nouvelle prévision
Une transaction « Sans prévision » peut devenir proposée ou rapprochée.

### REC-QLF-005 — Modification prévision
Réévaluation des qualifications concernées.

### REC-QLF-006 — Nouvelle récurrence
Les nouvelles occurrences peuvent faire évoluer une qualification existante.

## 6. Cycle de vie

### REC-LIFE-001
planned → overdue selon la date.

### REC-LIFE-002
transaction/occurrence compatibles → proposition.

### REC-LIFE-003
proposition → rapprochement confirmé.

### REC-LIFE-004
proposition → rejetée.

### REC-LIFE-005
occurrence ignored → remettre à traiter.

### REC-LIFE-006
occurrence planned/overdue → cancelled.

### REC-LIFE-007
rapprochement automatic → cancelled.

### REC-LIFE-008
rapprochement confirmed → cancelled.

### REC-LIFE-009
double rapprochement incompatible interdit.

### REC-LIFE-010
action incompatible non proposée et refusée côté service.

## 7. Panneau Proposition

### REC-PROP-001
Afficher les transactions membres.

### REC-PROP-002
Afficher les occurrences membres.

### REC-PROP-003
Afficher score et niveau de confiance.

### REC-PROP-004
Afficher écart de montant.

### REC-PROP-005
Afficher écart de date.

### REC-PROP-006
Afficher compte et sens.

### REC-PROP-007
Afficher similarité de libellé.

### REC-PROP-008
Le détail affiché doit correspondre au snapshot réellement enregistré.

## 8. KPI et vues

### REC-KPI-001 — À vérifier
Le nombre doit être exactement réconciliable avec les propositions accessibles.

### REC-KPI-002 — Prévisions ouvertes
Le nombre doit être réconciliable avec la population affichée.

### REC-KPI-003 — Sans prévision
Le nombre doit correspondre aux transactions qualifiées sans prévision.

### REC-KPI-004 — Rapprochées
Le nombre doit correspondre aux rapprochements actifs selon la définition produit.

### REC-VUE-001 — Vue À vérifier
Transactions, occurrences et proposition affichées dans le même périmètre.

### REC-VUE-002 — Vue Rapprochées
Les deux côtés n'affichent que les membres liés.

### REC-VUE-003 — Vue Sans prévision
Aucune action manuelle obligatoire pour chaque transaction.

### REC-VUE-004 — Vue Prévisions ouvertes
Le comportement du panneau Transactions reste explicite et cohérent.

## 9. Filtres

### REC-FLT-001
Tous les comptes.

### REC-FLT-002
Compte unique.

### REC-FLT-003
Période Du/Au.

### REC-FLT-004
Compte + période.

### REC-FLT-005
Statut + compte + période.

### REC-FLT-006
Retour à la vue globale.

**Invariant :** le dataset global avant et après les filtres est inchangé.

## 10. Traçabilité

### REC-AUD-001
Proposition créée : score, critères, date, membres.

### REC-AUD-002
Validation manuelle historisée.

### REC-AUD-003
Rapprochement automatique historisé.

### REC-AUD-004
Annulation historisée avec motif.

### REC-AUD-005
Ignore/réactivation historisés.

### REC-AUD-006
Afficher les informations présente des données métier, pas seulement un ID technique.

## 11. N↔N

### REC-GRP-001 — 1 transaction ↔ N occurrences
Totaux, membres, écart, score et annulation.

### REC-GRP-002 — N transactions ↔ 1 occurrence
Même contrôles.

### REC-GRP-003 — N↔N
Membres, total réel, total prévu, écart global, audit et annulation.

## 12. Intégrité des données

### REC-DATA-001
Un rapprochement ne modifie pas amount/date/account/sens de la transaction.

### REC-DATA-002
Suppression d'une transaction rapprochée libère proprement les liens.

### REC-DATA-003
Suppression d'un lot d'import libère tous les rapprochements concernés.

### REC-DATA-004
Modification d'une transaction devenue incompatible invalide ou réévalue le rapprochement.

### REC-DATA-005
Aucun lien orphelin après annulation/suppression.

## 13. Prévisionnel

### REC-FCST-001
Rapprochement auto : pas de double comptage prévu + réalisé.

### REC-FCST-002
Rapprochement manuel : même contrôle.

### REC-FCST-003
Proposition non confirmée : comportement conforme à la règle produit.

### REC-FCST-004
Annulation : restauration cohérente.

### REC-FCST-005
Occurrence ignorée/annulée : comportement cohérent.

## 14. Volumétrie

Tester au minimum :
- 10 ;
- 100 ;
- 500 ;
- 501 ;
- 1 000 ;
- 10 000 transactions.

### REC-PERF-001
Ouverture et filtrage sans erreur.

### REC-PERF-002
Aucune perte silencieuse liée à une limite d'affichage.

### REC-PERF-003
Un KPI supérieur à la limite d'affichage reste navigable et explicable.

## 15. Scénarios E2E obligatoires

### REC-E2E-001 — Auto
Créer récurrence → occurrence → importer transaction exacte → auto → détails → prévisionnel → annuler → état restauré.

### REC-E2E-002 — Ambigu
Deux prévisions crédibles → import → À vérifier → choisir → confirmer → audit.

### REC-E2E-003 — Sans prévision
Import sans prévision → without_forecast → créer récurrence → réévaluer → proposition ou auto.

### REC-E2E-004 — Manuel
Rejouer la qualification avec une transaction saisie manuellement.

### REC-E2E-005 — Ignore/réactive
Cas de non-régression issue #58.

### REC-E2E-006 — Annulation occurrence
Cas de non-régression issue #59.

### REC-E2E-007 — Audit
Cas de non-régression issue #60.

### REC-E2E-008 — Cohérence vues
Cas de non-régression issue #61.

## 16. Priorités

### P0
- intégrité transaction ;
- qualification import + manuel ;
- même compte/sens ;
- ambiguïté ;
- sans prévision ;
- double rapprochement ;
- annulation ;
- réévaluation ;
- filtres sans effet métier ;
- cohérence KPI/listes ;
- audit minimum ;
- anti-double comptage ;
- migration non destructive.

### P1
- paramétrage complet ;
- panneau proposition ;
- réactivation/annulation occurrence ;
- historique détaillé ;
- menus dépendants de l'état ;
- volumétrie ≥ 1 000.

### P2
- détection récurrence potentielle ;
- apprentissage par historique ;
- UX N↔N avancée.

La **compatibilité du modèle N↔N** est requise dès la refonte.

## 17. Critères d'entrée en recette

- tests unitaires P0 verts ;
- tests d'intégration P0 verts ;
- migration depuis base R7.2 validée ;
- fixtures versionnées ;
- commit/version identifiés ;
- aucune altération de transaction source.

## 18. Critères de sortie

- 100 % des P0 OK ;
- aucun P0 ouvert ;
- aucun P1 d'intégrité/cohérence ouvert ;
- tous les KPI réconciliables ;
- décisions explicables et auditables ;
- import et saisie manuelle équivalents ;
- ambiguïtés correctement détectées ;
- filtres sans effet métier ;
- prévisionnel cohérent ;
- non-régressions #58 à #61 couvertes ;
- exigences #57 implémentées ou explicitement exclues de la version.

## 19. Règle de gestion des anomalies

Toute anomalie corrigée doit ajouter ou renforcer au moins un test automatisé de non-régression.

Convention recommandée :
- issue #58 → test identifié REC-LIFE-005 / REC-E2E-005 ;
- issue #59 → REC-LIFE-006 / REC-E2E-006 ;
- issue #60 → REC-AUD-006 / REC-E2E-007 ;
- issue #61 → REC-VUE-002 / REC-E2E-008.
