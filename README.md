# Valoria Vision MVP V0.6.6

## V0.6.6 — Catégories avec sens Recette / Dépense

Cette version ajoute un **sens métier** aux catégories.

### Ajouts

- colonne `direction` dans les catégories ;
- sens disponibles : Recette, Dépense, Neutre ;
- saisie des transactions manuelles en montant positif ;
- saisie des récurrences en montant positif ;
- application automatique du signe selon la catégorie ;
- Budgets alimenté uniquement par les catégories de sens Dépense.

### Important

Les imports bancaires conservent leur signe d'origine.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Gestion des catégories

Cette version ajoute une gestion centralisée des catégories dans Paramètres.

### Ajouts

- onglet `Paramètres > Catégories` ;
- création, modification, suppression des catégories ;
- catégories reflétées dans le module Budgets ;
- listes de catégories dynamiques dans Transactions et Prévisionnel ;
- répercussion des renommages dans transactions, récurrences et budgets.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Optimisation chargement Plotly

Cette version réduit la latence visible lors de l’affichage des graphiques.

### Corrections principales

- Plotly.js n’est plus chargé depuis le CDN à chaque graphique ;
- un fichier local `data/runtime/plotly.min.js` est créé automatiquement au premier usage ;
- les graphiques sont rendus après l’affichage de la page pour améliorer la perception de vitesse ;
- un placeholder léger s’affiche immédiatement pendant le chargement du graphique.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Prévisionnel : graphique combiné crédits / débits / solde

Cette version modifie le graphique principal du Prévisionnel.

### Ajouts

- service central `ForecastChartService` ;
- graphique combiné Plotly : crédits, débits, solde ;
- vue quotidienne / vue mensuelle ;
- alimentation par le moteur de prévisionnel existant ;
- filtre compte, période et scénario ;
- infobulles détaillées ;
- clic sur une période pour ouvrir les opérations ;
- clic droit sur une période pour gérer les récurrences.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Plotly interactif & légendes donuts

Cette version corrige deux points importants :

- les légendes des donuts sont placées sur le côté droit ;
- le Prévisionnel utilise à nouveau un graphique Plotly premium, mais avec les interactions métier restaurées.

### Prévisionnel

- survol : détail solde / entrées / sorties / opérations ;
- clic : popup des opérations du jour ;
- clic droit : menu contextuel de gestion des récurrences.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Prévisionnel interactif restauré

Cette version corrige le remplacement excessif du graphique Prévisionnel.

### Correction principale

Le Prévisionnel repasse sur son graphique interactif natif PySide6 afin de conserver :

- détail des opérations au survol / clic ;
- popup des opérations du jour ;
- clic droit sur la courbe ;
- menu contextuel de gestion des récurrences.

### Décision technique

Valoria Vision adopte une approche hybride :

- Plotly pour les graphiques premium de consultation ;
- graphique natif PySide6 quand l’interaction métier est indispensable.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Correction layout Plotly

Cette version corrige les problèmes de chevauchement et poursuit le déploiement Plotly.

### Corrections principales

- Dashboard plus compact ;
- donuts avec légende propre ;
- Budgets : deux graphiques côte à côte ;
- Budgets : prévu/réalisé en barres horizontales ;
- Prévisionnel : courbe Plotly premium ;
- Patrimoine : graphiques Plotly dans la vue globale ;
- composant Plotly renforcé pour éviter les scrollbars internes.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Remplacement progressif des graphiques

Cette version commence le remplacement des graphiques historiques par Plotly dans les vrais écrans métiers.

### Remplacements intégrés

- Dashboard :
  - trésorerie prévisionnelle ;
  - répartition du patrimoine ;
  - répartition des dépenses.
- Budgets :
  - prévu / réalisé ;
  - taux d’utilisation par catégorie.

### Ajout technique

- composant réutilisable `PlotlyFigureCard`.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Correctif Treemap réel Plotly

Cette version corrige l’affichage du Treemap patrimoine réel dans `Paramètres > Charts réels`.

### Correction

- ajout d’identifiants uniques Plotly ;
- parents du treemap raccordés par ids ;
- meilleure robustesse avec les données réelles ;
- aucun impact sur les autres graphiques.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Raccord Plotly aux vraies données

Cette version raccorde le laboratoire Plotly aux données réelles.

### Ajouts

- donut dépenses réelles ;
- treemap patrimoine réel ;
- courbe de trésorerie prévisionnelle réelle ;
- graphique budget prévu / réalisé réel ;
- onglet renommé `Charts réels`.

### Important

Les anciens graphiques ne sont pas encore remplacés.  
Cette phase valide uniquement le raccord Plotly aux données métier réelles.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Correctif Treemap Plotly

Cette version corrige le graphique `Treemap — patrimoine fictif` du laboratoire charts.

### Correction

- valeur racine du treemap corrigée ;
- structure parent/enfant rendue compatible avec Plotly ;
- le graphique ne doit plus rester blanc.


# Valoria Vision MVP V0.6.6

## V0.6.6 — Laboratoire charts Plotly

Cette version ajoute un laboratoire isolé pour tester Plotly comme moteur de graphiques premium.

### Ajouts

- onglet `Laboratoire charts` dans Paramètres ;
- intégration Plotly dans PySide6 via QWebEngineView ;
- donut fictif ;
- treemap fictif ;
- courbe de trésorerie fictive ;
- graphique budget prévu / réalisé fictif ;
- fallback propre si Plotly ou QWebEngineView n’est pas disponible.

### Important

Cette phase utilise des données fictives.  
Aucun graphique existant n’est remplacé en V0.6.6.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Budgets V1

Cette version ajoute le premier module Budgets fonctionnel.

### Ajouts

- écran Budgets raccordé au menu latéral ;
- budgets mensuels par catégorie ;
- comparaison prévu / réalisé ;
- calcul du reste disponible ;
- taux d’utilisation ;
- alertes de dépassement et de vigilance ;
- reprise automatique du mois précédent ;
- édition rapide des budgets ;
- règles métier centralisées dans la couche database.

### Important

Les montants réalisés sont calculés à partir des transactions réelles du mois.  
Les transferts internes, revenus et investissements sont exclus des dépenses courantes.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Paramètres : navigation par onglets & volet latéral

Cette version réorganise l’écran Paramètres.

### Ajouts

- navigation par onglets ;
- volet latéral droit de détail ;
- séparation entre Vue d’ensemble, Sécurité, Diagnostic, Cohérence métier et Maintenance ;
- affichage principal plus compact ;
- rapports longs déplacés dans le volet.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Correctif vault chiffré au démarrage

Cette version corrige le crash observé au lancement de la V0.5.0 :

`SecurityIntegrityError: Clé invalide ou sauvegarde altérée`

### Cause

Un fichier vault chiffré `.vvdb` peut être présent dans le dossier `data/secure/` alors qu’il a été généré avec une autre clé locale. Dans ce cas, il ne doit pas bloquer le démarrage.

### Correction

- le vault illisible est déplacé en quarantaine dans `data/backups/` ;
- l’application poursuit son initialisation normalement ;
- aucun fichier `.vvdb` ni clé locale de développement n’est inclus dans le ZIP distribué ;
- le numéro de version de l’installateur passe en V0.6.0.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Socle Premium & évolutivité long terme

Cette version prépare l’application aux évolutions futures sans modifier le périmètre fonctionnel visible.

### Ajouts

- feature flags Premium ;
- multi-devises préparatoire ;
- multi-langues préparatoire ;
- UUID techniques ;
- `deleted_at`, `sync_status`, `external_id`, `external_source` ;
- préférences utilisateur centralisées ;
- audit trail ;
- préparation Open Banking / synchronisation future ;
- diagnostic Paramètres enrichi.

### Important

Les fonctionnalités Premium restent désactivées par défaut.  
La devise active reste EUR.  
La langue active reste FR.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Mot de passe maître & verrouillage session

Cette version complète la phase Security Foundation locale.

### Ajouts

- création du mot de passe maître au premier lancement ;
- déverrouillage obligatoire aux lancements suivants ;
- hash PBKDF2-HMAC-SHA256 salé ;
- bouton `Verrouiller` dans le menu latéral ;
- verrouillage automatique après inactivité ;
- diagnostic sécurité enrichi.

### Important

Le mot de passe n’est pas stocké en clair. Seuls le sel, le hash et les paramètres de dérivation sont conservés.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Chiffrement base & sauvegardes

Cette version démarre le chiffrement local prévu par la roadmap sécurité.

### Ajouts

- vault chiffré de la base : `data/secure/valoria_vision.vvdb`
- sauvegardes chiffrées `.vvb`
- restauration des sauvegardes `.vvb`
- support des anciennes sauvegardes `.db`
- dépendances sécurité : `cryptography` et `keyring`
- diagnostic Paramètres mis à jour
- installateur corrigé en V0.6.0

### Important

Le mot de passe maître et le verrouillage de session arrivent en V0.6.0.
La bêta avec données réelles reste donc en NO-GO jusqu’à la fin de V0.6.0.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Gel socle & audit sécurité

Cette version ouvre la phase Security Foundation.

### Objectifs

- Geler la V0.4.20 comme socle fonctionnel validé.
- Cartographier les données sensibles.
- Cartographier les fichiers et tables à protéger.
- Préparer la décision technique pour le chiffrement.
- Ajouter un premier résumé d’audit sécurité dans Paramètres > Diagnostic.

### Livrables

Disponibles dans `docs/security/`.

### Décision

La bêta privée avec données réelles reste en NO-GO tant que :
- la base locale n’est pas chiffrée ;
- les sauvegardes ne sont pas chiffrées ;
- l’accès applicatif n’est pas protégé par mot de passe maître.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Prévisionnel : volet latéral droit d’analyse

Cette version remplace le panneau fixe `Lecture de la période` par un volet latéral droit ouvrable au clic.

### Objectifs

- libérer l’espace de la courbe de trésorerie ;
- supprimer définitivement les superpositions dans le panneau d’analyse ;
- afficher les informations détaillées dans un espace plus confortable ;
- ouvrir/fermer l’analyse à la demande.

### Nouveau comportement

- Bouton `Analyse de la période` dans l’en-tête du Prévisionnel.
- Clic sur le bouton : ouverture du volet latéral droit.
- Clic sur `×` ou `Masquer l’analyse` : fermeture du volet.
- La courbe utilise toute la largeur quand le volet est fermé.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Correctifs d'affichage Prévisionnel

- Passage de la barre de filtres du Prévisionnel sur une grille à 2 lignes pour supprimer la troncature du sélecteur de compte bancaire.
- Correction du panneau « Lecture de la période » : la règle d'alerte est désormais affichée dans un bloc structuré, sans superposition avec les blocs suivants.
- Ajustement des largeurs minimales et des politiques de taille sur les sélecteurs du Prévisionnel.

# Valoria Vision MVP V0.6.0

## V0.6.0 — Correctifs UI filtres & alertes

Cette version corrige les anomalies visuelles constatées après la V0.4.17.

### Corrections

- Restauration d’un vrai bouton visible à droite des menus déroulants.
- Ajout d’une flèche SVG visible dans les `QComboBox` et `QDateEdit`.
- Largeurs minimales renforcées sur les filtres Prévisionnel, Transactions et Comptes.
- Correction du bloc d’alerte du Prévisionnel afin qu’il ne tronque plus les informations.
- Le cartouche d’alerte utilise maintenant une mise en page en bloc, et non plus un seul label HTML contraint.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Correctif démarrage Patrimoine

Cette version corrige le crash au lancement de la V0.4.16 :

`NameError: name 'QHeaderView' is not defined`

### Correction

- Ajout de l’import `QHeaderView` dans `app/ui/assets_page.py`.
- Ajout de l’import `QFrame` dans `app/ui/transactions_page.py` après contrôle statique.
- L’écran `Patrimoine` peut maintenant construire ses tableaux correctement.
- Conservation des corrections d’affichage de la V0.4.15 et du correctif V0.4.16.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Correctif démarrage Prévisionnel

Cette version corrige le crash au lancement de la V0.4.15 :

`NameError: name 'QFrame' is not defined`

### Correction

- Ajout de l’import `QFrame` dans `app/ui/forecast_page.py`.
- Le panneau `Lecture de la période` peut maintenant être construit correctement.
- Conservation des corrections d’affichage de la V0.4.15.


# Valoria Vision MVP V0.6.0

## V0.6.0 — Correctifs d’affichage : selecteurs, panneaux et lisibilité

- correction du rendu des sélecteurs QComboBox / QDateEdit (finitions à droite, padding, largeur utile) ;
- sécurisation des largeurs minimales sur les barres de filtres ;
- élargissement et meilleure mise en page du panneau « Lecture de la période » ;
- amélioration du retour à la ligne dans les blocs texte du Prévisionnel ;
- amélioration de la lisibilité des synthèses Patrimoine et Top actifs.

1. Diagnostic renforcé dans `Paramètres`
   - intégrité SQLite ;
   - version de schéma ;
   - nombre de comptes, transactions, imports, récurrences et actifs ;
   - cohérence revenus Dashboard / Transactions ;
   - cohérence dépenses Dashboard / Transactions ;
   - point bas prévisionnel et alerte.

2. Courbes vérifiables
   - tooltip sur courbe Dashboard ;
   - tooltip sur courbe Patrimoine ;
   - date, valeur et variation du point.

3. Prévisionnel
   - règle d’alerte point bas explicitée ;
   - critique sous 0 € ;
   - vigilance sous 5 000 € ;
   - OK au-dessus du seuil.

4. Récurrences
   - tableaux harmonisés ;
   - suppression des traits/focus parasites ;
   - sélection par ligne complète.

5. Fichiers de recette ajoutés dans `data/`
   - `test_invalid_database.db` ;
   - `import_test_500_transactions.csv` ;
   - `README_TESTS_V0_4_14.txt`.


## V0.6.0 — Recette V0.4.12 & correctifs métier/UI

Cette version regroupe les corrections issues du premier fichier de recette.

### Corrections intégrées

1. Revenus vrais :
   - un revenu = montant positif + catégorie `Revenus`.

2. Dépenses courantes :
   - règle métier centralisée et appliquée au Dashboard.

3. Filtre période Transactions :
   - `Toutes périodes`
   - période fixe `01/06/2026 - 23/06/2026`
   - `30 derniers jours`
   - `Mois courant`
   - `Année courante`

4. Onglet `À catégoriser` :
   - statut `À catégoriser`
   - catégorie vide
   - catégorie `À catégoriser`

5. Bouton `Voir transactions` :
   - depuis Comptes, ouvre Transactions avec le compte filtré.

6. Vue Comptes :
   - activation de `Vue tableau`
   - activation de `Vue cartes`


## V0.6.0 — Patrimoine : tableaux harmonisés

Cette version corrige l’affichage des lignes dans les tableaux du patrimoine.

### Correction

Le tableau `Top actifs` ne devait pas afficher de traits noirs ou de focus cellule.

Il respecte maintenant la même règle UI que les transactions :

- sélection par ligne ;
- fond bleu doux sur la ligne sélectionnée ;
- pas de bordure noire sur cellule ;
- pas de focus cellule visible ;
- alternance légère des lignes ;
- présentation homogène avec les autres tableaux.

Cette correction s’applique aux tableaux :

- `Actifs`
- `Passifs`
- `Top actifs`


## V0.6.0 — Patrimoine : navigation par onglets enrichie

Cette version améliore l’écran `Patrimoine`.

### Ajouts

- Onglet `Synthèse intelligente`
- Onglet `Top actifs`

### Objectif

Éviter d’avoir à dérouler la vue globale pour consulter les informations importantes.

### Nouveau comportement

`Vue globale` affiche uniquement les graphiques de synthèse.

Les blocs suivants sont déplacés dans des onglets dédiés :

- `Synthèse intelligente`
- `Top actifs`

Le classement des actifs est maintenant aussi disponible sous forme de tableau.


## Correctif V0.6.0 — Sécurisation base SQLite

Cette version corrige le crash :

`sqlite3.DatabaseError: file is not a database`

### Comportement ajouté

Au démarrage, Valoria Vision vérifie le fichier :

`data/valoria_vision.db`

Si ce fichier n’est pas une base SQLite valide :

1. il est déplacé dans `data/backups/` ;
2. une nouvelle base propre est recréée ;
3. l’application continue de fonctionner.

Le fichier invalide n’est pas supprimé.


## Correctif V0.6.0

- Ajout d’une échelle de temps lisible sur la courbe du Dashboard.
- Ajustement de la carte `Synthèse rapide` : meilleure séparation entre libellés et chiffres.
- Harmonisation visuelle de la liste des comptes avec l’écran Transactions.
- Suppression des traits noirs de focus/hover sur les lignes du tableau Comptes.


## Objectif de la version

V0.6.0 corrige le flux d'import bancaire de la V0.3.0 tout en conservant le **socle technique & métier consolidé**.

Cette version conserve les 4 écrans validés en V0.2.x et renforce les fondations avant d'ajouter de nouveaux modules.

## Périmètre intégré

### Base SQLite
- Base renommée `valoria_vision.db`.
- Table `schema_meta` pour suivre la version de schéma.
- Tables consolidées : comptes, transactions, lots d'import, patrimoine, valorisations, catégories, paramètres.
- Migrations légères pour préserver les bases existantes.

### Calculs métier
- Règles de calcul isolées dans `app/services/business_rules.py`.
- Soldes actuels calculés à partir du solde de référence + mouvements postérieurs.
- KPI Dashboard et Comptes basés sur les soldes calculés.

### Transactions
- Ajout manuel d'une transaction.
- Suppression de la transaction sélectionnée.
- Conservation de l'import bancaire avec aperçu détaillé, doublons et annulation d'import.

### Comptes
- Ajout de compte conservé.
- Mise à jour du solde de référence depuis le volet détail.

### Paramètres
- Nouvel écran Paramètres opérationnel.
- Sauvegarde locale de la base SQLite.
- Restauration d'une sauvegarde.
- Contrôle technique simple de la base.

## Installation

1. Dézipper le dossier.
2. Double-cliquer sur `install.bat`.
3. Double-cliquer sur `run.bat`.

## Validation recommandée

Utiliser le pack `CashPilot_Batteries_Tests_V0_3.zip` déjà préparé pour tester :
- démarrage ;
- comptes ;
- imports ;
- soldes ;
- dashboard ;
- patrimoine ;
- sauvegarde/restauration ;
- non-régression des 4 écrans validés.


## Correctif V0.6.0

Flux d'import attendu :

1. Cliquer sur `Choisir un fichier bancaire`.
2. Vérifier le bloc `Analyse du fichier`.
3. Cliquer sur `Voir l’aperçu détaillé` pour contrôler les lignes.
4. Cliquer sur `4. Importer les opérations` pour importer directement après confirmation.
5. Les transactions et l’historique des imports se rafraîchissent automatiquement.


## Correctif V0.6.0

Cette version corrige le crash constaté lors de l’ouverture de l’aperçu détaillé d’un fichier bancaire :

`NameError: name 'row' is not defined`

Le problème venait d’un identifiant de transaction appliqué par erreur au tableau d’aperçu avant import, alors que ces lignes ne sont pas encore enregistrées en base.


## Correctif V0.6.0

L’historique des imports identifie maintenant les lots avec l’identifiant bancaire/IBAN du compte.

Exemple d’affichage :

`Compte : FR7630…236554 — BNP — BNP`

Cela évite la confusion entre deux imports associés à des comptes portant des noms proches.


## Correctif V0.6.0

L’écran Patrimoine utilise maintenant les données réelles de valorisation :

- `Répartition des actifs` : calculée depuis les éléments patrimoniaux actifs en base.
- `Évolution du patrimoine net` : calculée depuis l’historique `asset_values`, et non plus depuis une série de démonstration figée.

Cela évite les incohérences visuelles entre les KPI, le donut et la courbe.


## V0.6.0 — Multi-sélection & actions groupées

Cette version ajoute les premières fonctions de maintenance groupée, en priorité sur l’écran Transactions.

### Utilisation

1. Aller dans `Transactions`.
2. Cocher une ou plusieurs lignes dans la première colonne.
3. Utiliser la barre d’actions qui apparaît au-dessus du tableau.
4. Ou faire un clic droit sur le tableau pour ouvrir le menu contextuel.

### Actions disponibles

- Modifier la catégorie de plusieurs transactions.
- Marquer plusieurs transactions comme validées.
- Marquer plusieurs transactions à catégoriser.
- Supprimer plusieurs transactions en une seule manipulation.

### Sécurité

La suppression groupée demande une confirmation explicite.


## V0.6.0 — Prévisionnel de trésorerie

Cette version active l’écran `Prévisionnel`.

### Fonctions intégrées

- Projection de trésorerie à 30, 60 et 90 jours.
- Scénarios : Prudent, Réaliste, Optimiste.
- Récurrences de revenus et charges.
- Échéances à venir.
- Courbe de cash prévisionnelle.
- Alertes de point bas.

### Mode opératoire de test

1. Ouvrir l’écran `Prévisionnel`.
2. Vérifier les KPI.
3. Tester les horizons 30 / 60 / 90 jours.
4. Tester les scénarios Prudent / Réaliste / Optimiste.
5. Ajouter une récurrence.
6. Vérifier que la courbe et les échéances sont recalculées.


## V0.6.0 — Prévisionnel en popups

Cette version améliore l’ergonomie de l’écran Prévisionnel.

Les listes détaillées ne sont plus affichées en bas de page. Elles sont accessibles via :

- le bouton `Voir échéances` ;
- le bouton `Voir récurrences` ;
- le bouton `Détail courbe` ;
- ou par clic droit sur la courbe prévisionnelle.

### Test recommandé

1. Ouvrir `Prévisionnel`.
2. Vérifier que l’écran principal est lisible sans devoir descendre en bas de page.
3. Cliquer sur `Voir échéances`.
4. Cliquer sur `Voir récurrences`.
5. Cliquer sur `Détail courbe`.
6. Faire un clic droit sur la courbe et tester les trois choix du menu contextuel.


## V0.6.0 — Prévisionnel quotidien interactif

Cette version corrige la logique d’affichage du prévisionnel.

### Corrections

- La courbe affiche un point par jour sur toute la période sélectionnée.
- Les boutons redondants de l’en-tête ont été supprimés.
- Les détails ne s’affichent plus sous forme de listes générales.
- Un clic ou un survol sur un jour de la courbe affiche uniquement les opérations de cette journée.

### Test recommandé

1. Ouvrir `Prévisionnel`.
2. Choisir une période 30 / 60 / 90 jours.
3. Vérifier que la courbe contient un point par jour.
4. Survoler plusieurs jours.
5. Cliquer sur un point avec opérations.
6. Vérifier que le popup ne contient que les opérations du jour sélectionné.


## V0.6.0 — Gestion des récurrences

Cette version permet enfin de maintenir les récurrences déjà créées.

### Ajouts
- bouton **Gérer les récurrences** dans l’en-tête du prévisionnel ;
- popup **Récurrences par compte bancaire** ;
- modification / suppression d’une récurrence ;
- clic droit sur la courbe pour gérer les récurrences présentes sur la journée pointée ;
- clic droit dans le popup journalier pour gérer une récurrence sélectionnée.

### Test conseillé
1. Ajouter une récurrence.
2. Vérifier qu’elle apparaît sur la courbe.
3. Ouvrir le popup du jour correspondant.
4. Clic droit sur la ligne de récurrence → Modifier / Supprimer.
5. Ouvrir **Gérer les récurrences** et vérifier le filtre par compte bancaire.


## V0.6.0 — Filtre par compte bancaire

### Ajout
- nouveau sélecteur **Compte bancaire** dans la barre de filtres du prévisionnel.

### Effet
- la courbe, les KPI et les opérations de la période peuvent être calculés :
  - soit sur **tous les comptes** ;
  - soit sur **un seul compte bancaire** sélectionné.

### Test conseillé
1. Ouvrir **Prévisionnel de trésorerie**.
2. Changer le filtre **Compte bancaire**.
3. Vérifier que la courbe et les KPI changent.
4. Vérifier que les opérations du popup journalier correspondent bien au compte choisi.


## V0.6.0 — Sélection comptes dynamique

Cette version corrige le filtre `Compte bancaire` du Prévisionnel.

### Problème corrigé
Si un compte était créé après l’ouverture de l’application, il pouvait ne pas apparaître dans la liste du Prévisionnel car cette liste était initialisée une seule fois au démarrage.

### Correction
La liste des comptes est maintenant rafraîchie :
- à chaque retour sur l’écran Prévisionnel ;
- avant recalcul de la courbe ;
- depuis la base SQLite courante.

### Test conseillé
1. Créer un nouveau compte dans `Comptes`.
2. Importer ou ajouter des opérations.
3. Aller dans `Prévisionnel`.
4. Ouvrir la liste `Compte bancaire`.
5. Vérifier que le nouveau compte apparaît.
6. Le sélectionner et vérifier que la courbe se recalcule.


## V0.6.0 — Récurrences cohérentes

### Corrections
- Une récurrence de loyer saisie à `-600 €` reste affichée à `-600 €`.
- Le scénario `Prudent` ne majore plus silencieusement les sorties à `-648 €`.
- Le scénario `Optimiste` ne majore plus silencieusement les entrées.
- L’onglet `Transactions > Récurrentes` affiche maintenant les vraies récurrences créées dans le prévisionnel.

### Test conseillé
1. Créer une récurrence de loyer à `-600 €`.
2. Sélectionner le compte concerné dans `Prévisionnel`.
3. Pointer la journée de loyer sur la courbe.
4. Vérifier que le popup affiche bien `-600 €`.
5. Aller dans `Transactions`.
6. Ouvrir l’onglet `Récurrentes`.
7. Vérifier que la récurrence apparaît.


## V0.6.0 — Solde initial & historique des soldes

Cette version ajoute une règle métier fondamentale :

`Solde à une date = solde initial + transactions entre la date initiale et la date observée`

### Exemple

Compte BNP :
- date initiale : 2026-01-01
- solde initial : 500 €
- transactions importées en juin : +4 161 €

Alors :
- janvier à mai : 500 €
- après les transactions de juin : 4 661 €

### Changements techniques

Les règles sont centralisées dans :

`app/services/business_rules.py`

Fonctions ajoutées :
- `balance_at_date`
- `current_balance`
- `balance_series`
- `summarize_accounts_at_date`

### Changements base SQLite

Ajout sur la table `accounts` :
- `initial_balance`
- `initial_date`

Les anciens champs `reference_balance/reference_date` sont conservés comme alias de compatibilité.

### Test conseillé

1. Créer un compte BNP avec une date initiale en janvier 2026 et un solde initial de 500 €.
2. Importer des transactions en juin.
3. Aller dans Prévisionnel.
4. Sélectionner BNP.
5. Choisir une date de départ avant juin.
6. Vérifier que la courbe démarre à 500 € et évolue uniquement aux dates des transactions.
7. Vérifier que le solde actuel reste bien à 4 661 € après import.


## V0.6.0 — Dashboard raccordé au réel

Cette version corrige la courbe principale du Dashboard.

### Avant
La courbe était encore construite avec des séries de démonstration :

- optimiste ;
- réaliste ;
- prudent.

### Maintenant
La courbe est calculée depuis le moteur prévisionnel réel :

`cash_forecast()`

Elle tient donc compte :

- des soldes initiaux ;
- de l’historique réel des transactions ;
- des transactions futures ;
- des récurrences ;
- des règles métier centralisées.

### KPI corrigé
Le KPI `Liquidités prévisionnelles J+30` n’est plus calculé avec un +3 900 € codé en dur.  
Il utilise désormais le solde projeté réel à J+30.

### Test conseillé
1. Aller dans `Dashboard`.
2. Vérifier que la courbe n’affiche plus une progression artificielle.
3. Modifier ou supprimer une récurrence.
4. Revenir au Dashboard.
5. Vérifier que la courbe et le KPI J+30 se recalculent.
6. Comparer avec l’écran `Prévisionnel` : les tendances doivent être cohérentes.
