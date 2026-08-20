## V0.6.6 — Catégories avec sens Recette / Dépense
- Ajout de la colonne `direction` dans `categories`.
- Ajout du sens Recette / Dépense / Neutre dans Paramètres > Catégories.
- Les transactions manuelles n'ont plus besoin d'un montant signé.
- Les récurrences n'ont plus besoin d'un montant signé.
- Les montants sont normalisés automatiquement selon le sens de la catégorie.
- Le module Budgets utilise les catégories de sens Dépense activées budget.
- Les imports bancaires conservent leur signe d'origine.

## V0.6.6 — Gestion des catégories
- Ajout de l’onglet Paramètres > Catégories.
- Ajout/modification/suppression des catégories.
- Ajout des champs `budget_enabled`, `deleted_at`, `uuid`, `updated_at` sur les catégories.
- Les catégories sont répercutées dans Transactions, Prévisionnel et Budgets.
- Renommage d’une catégorie : mise à jour transactions, récurrences et budgets.
- Suppression d’une catégorie : transactions/récurrences vers À catégoriser, budgets liés désactivés.
- Schéma technique V8.

## V0.6.6 — Optimisation chargement Plotly
- Ajout de `app/ui/plotly_runtime.py`.
- Chargement local de Plotly.js au lieu du CDN.
- Rendu différé des graphiques Plotly pour laisser la page apparaître plus vite.
- Ajout de placeholders de chargement.
- Application aux graphiques Dashboard/Budgets/Patrimoine, Charts réels et Prévisionnel combiné.

## V0.6.6 — Prévisionnel : graphique combiné crédits / débits / solde
- Ajout du service `ForecastChartService`.
- Ajout d’une vue quotidienne et mensuelle pour le graphique Prévisionnel.
- Remplacement de la courbe simple par un graphique combiné : crédits, débits et solde.
- Raccord du graphique aux filtres compte, scénario et période.
- Ajout d’infobulles détaillées.
- Préparation et raccord du clic période vers le détail des opérations.
- Clic droit conservé pour la gestion des récurrences de la période.

## V0.6.6 — Plotly interactif & légendes donuts
- Déplacement des légendes de donuts sur le côté droit.
- Ajout d’un graphique Plotly interactif dans Prévisionnel.
- Ajout d’un bridge Qt WebChannel pour les clics Plotly.
- Restauration du clic popup jour et du clic droit récurrences sur le nouveau graphique.
- Suppression du menu navigateur par défaut sur le graphique Prévisionnel.

## V0.6.6 — Prévisionnel interactif restauré
- Restauration du graphique natif interactif dans l’écran Prévisionnel.
- Restauration du survol/clic permettant d’afficher les opérations du jour.
- Restauration du clic droit et du menu contextuel des récurrences.
- Décision d’architecture hybride : Plotly pour lecture premium, PySide6 natif pour interactions métier fortes.

## V0.6.6 — Correction layout Plotly
- Correction des chevauchements sur le Dashboard.
- Compactage du composant PlotlyFigureCard.
- Suppression des scrollbars internes des vues Plotly.
- Réorganisation des graphiques Budgets en deux colonnes.
- Orientation horizontale compacte pour le prévu/réalisé Budgets.
- Ajout d'une courbe Plotly dans Prévisionnel.
- Remplacement des graphiques principaux Patrimoine par Plotly.

## V0.6.6 — Remplacement progressif des graphiques
- Ajout du composant `PlotlyFigureCard`.
- Remplacement des graphiques principaux du Dashboard par Plotly.
- Ajout de graphiques Plotly dans Budgets.
- Conservation du laboratoire `Charts réels`.
- Aucun changement de règle métier.

## V0.6.6 — Correctif Treemap réel Plotly
- Correction du Treemap patrimoine réel qui pouvait rester blanc.
- Ajout d’ids uniques Plotly pour éviter les ambiguïtés labels/parents.
- Parents du treemap raccordés par ids.
- Aucun changement métier.

## V0.6.6 — Raccord Plotly aux vraies données
- Raccord du laboratoire Plotly aux transactions réelles.
- Raccord du treemap Plotly aux actifs/passifs réels.
- Raccord de la courbe Plotly au moteur réel de prévisionnel.
- Raccord du graphique budget prévu/réalisé aux budgets et transactions réelles.
- Renommage de l’onglet en `Charts réels`.
- Aucun graphique existant n’est encore remplacé.

## V0.6.6 — Correctif Treemap Plotly
- Correction du treemap patrimoine fictif qui pouvait rester blanc.
- Correction des valeurs parent/enfant avec `branchvalues="total"`.
- Ajout d’un affichage valeur/pourcentage dans le treemap.

## V0.6.6 — Laboratoire charts Plotly
- Ajout de l’onglet Paramètres > Laboratoire charts.
- Ajout du fichier `app/ui/charts_lab_page.py`.
- Intégration Plotly via QWebEngineView.
- Ajout de 4 graphiques fictifs : donut, treemap, courbe, budget prévu/réalisé.
- Ajout de `plotly` dans `requirements.txt`.
- Aucun graphique existant n’est remplacé dans cette phase.

## V0.6.0 — Budgets V1
- Ajout de la table `budgets`.
- Passage du schéma technique en V7.
- Ajout de la page `BudgetsPage`.
- Raccord du menu latéral au vrai module Budgets.
- Ajout des KPI Budget prévu, Réalisé, Reste disponible, Dépassements, Vigilances.
- Ajout des onglets Vue d’ensemble, Catégories, Alertes & règles.
- Ajout de l’édition rapide d’un budget par catégorie.
- Ajout du calcul prévu/réalisé depuis les transactions réelles.
- Exclusion des transferts, investissements et revenus des dépenses budgétaires.

## V0.6.0 — Paramètres : navigation par onglets & volet latéral
- Refonte de l’écran Paramètres.
- Ajout des onglets Vue d’ensemble, Sécurité, Diagnostic, Cohérence métier, Maintenance.
- Ajout d’un volet latéral droit de détail.
- Réduction des longs blocs verticaux.
- Conservation des actions sauvegarde/restauration.
- Meilleure lisibilité du diagnostic sécurité, métier et Premium.

## V0.6.0 — Correctif vault chiffré au démarrage
- Correction du crash `SecurityIntegrityError: Clé invalide ou sauvegarde altérée`.
- Ajout d’une quarantaine automatique des vaults `.vvdb` illisibles.
- Suppression des vaults/clefs locales du ZIP distribué.
- L’application peut redémarrer et recréer un vault local propre.
- Installateur mis à jour en V0.6.0.

## V0.6.0 — Socle Premium & évolutivité long terme
- Ajout des tables `feature_flags`, `currencies`, `translations`, `user_preferences`, `audit_log`.
- Ajout des UUID et champs de synchronisation sur les principales tables.
- Ajout de la préparation multi-devises.
- Ajout de la préparation multi-langues.
- Ajout des préférences utilisateur centralisées.
- Ajout d’un rapport `premium_foundation_report()`.
- Ajout d’un diagnostic Premium dans Paramètres.
- Ajout des services `money.py`, `feature_flags.py`, `i18n.py`.
- Passage du schéma technique en V6.

## V0.6.0 — Mot de passe maître & verrouillage session
- Ajout d’un service `AuthService`.
- Ajout de l’écran de création du mot de passe maître.
- Ajout de l’écran de déverrouillage.
- Hash PBKDF2-HMAC-SHA256 salé, sans stockage du mot de passe en clair.
- Ajout du bouton `Verrouiller` dans le menu latéral.
- Ajout du verrouillage automatique après inactivité.
- Diagnostic sécurité enrichi.

## V0.6.0 — Chiffrement base & sauvegardes
- Ajout d’un service `CryptoService`.
- Ajout d’un vault chiffré de la base : `data/secure/valoria_vision.vvdb`.
- Création de sauvegardes chiffrées `.vvb`.
- Restauration possible des `.vvb`.
- Support legacy des anciennes sauvegardes SQLite `.db`.
- Diagnostic sécurité mis à jour dans Paramètres.
- Ajout des dépendances `cryptography` et `keyring`.
- Correction du numéro de version affiché dans `install.bat`.

## V0.6.0 — Gel socle & audit sécurité
- Gel du socle fonctionnel validé V0.4.20.
- Ajout du dossier `docs/security/`.
- Ajout cartographie données sensibles.
- Ajout cartographie fichiers/tables.
- Ajout matrice de risques sécurité.
- Ajout matrice de décision chiffrement.
- Ajout checklist Go/No-Go bêta.
- Ajout `security_audit_report()` dans la couche database.
- Ajout résumé audit sécurité dans Paramètres > Diagnostic.

## V0.6.0 — Prévisionnel : volet latéral droit d’analyse
- Suppression du panneau fixe `Lecture de la période`.
- Ajout d’un bouton `Analyse de la période` dans l’en-tête du Prévisionnel.
- Ajout d’un volet latéral droit ouvrable/fermable.
- Migration de l’alerte, des règles d’alerte, du compte sélectionné, des opérations, récurrences et scénario dans le volet.
- La courbe reprend toute la largeur lorsque le volet est fermé.
- Objectif : supprimer les superpositions et gagner en lisibilité.

## V0.6.0 — Correctifs UI filtres & alertes
- Correction du style global des `QComboBox` et `QDateEdit`.
- Ajout d’une icône `chevron_down.svg` pour restaurer une flèche visible.
- Bouton déroulant visible à droite des sélecteurs.
- Largeurs minimales renforcées sur Prévisionnel, Transactions et Comptes.
- Correction du cartouche d’alerte Prévisionnel : plus de texte tronqué.
- Bloc d’alerte reconstruit avec `QFrame` + `QVBoxLayout` + labels séparés.

## V0.6.0 — Correctif démarrage Patrimoine
- Correction du crash V0.4.16 : `NameError: name 'QHeaderView' is not defined`.
- Ajout de `QHeaderView` aux imports de `app/ui/assets_page.py`.
- Ajout de `QFrame` aux imports de `app/ui/transactions_page.py` après contrôle statique.
- Ajout d’un contrôle statique des imports Qt évidents avant livraison.
- Compilation syntaxique complète de tous les fichiers Python validée.

## V0.6.0 — Correctif démarrage Prévisionnel
- Correction du crash V0.4.15 : `NameError: name 'QFrame' is not defined`.
- Ajout de `QFrame` aux imports de `app/ui/forecast_page.py`.
- Compilation syntaxique complète de tous les fichiers Python validée.

## V0.6.0 — Correctifs d’affichage : selecteurs, panneaux et lisibilité
- Correction visuelle des sélecteurs (QComboBox, QDateEdit) : plus de bouton droit tronqué ni de finition inachevée.
- Largeurs minimales ajoutées sur les filtres des écrans Prévisionnel et Transactions.
- Panneau « Lecture de la période » élargi et réorganisé pour éviter les textes tronqués.
- Bloc « Top actifs » du Patrimoine reformatté avec retour à la ligne plus propre.
- Tableaux Patrimoine mieux dimensionnés pour limiter les tronquages.

## V0.6.0 — Recette finale V0.4 : corrections de cohérence, courbes et diagnostic
- Ajout de tooltips sur les courbes génériques `LineChart` : Dashboard et Patrimoine deviennent vérifiables point par point.
- Ajout d’un format `euro_precise()` pour les écrans d’audit avec centimes.
- Renforcement du diagnostic Paramètres : intégrité SQLite, schéma, volumes, cohérence revenus/dépenses Dashboard vs Transactions, point bas prévisionnel.
- Ajout d’un diagnostic d’écart sur les dépenses et revenus du mois.
- Clarification des alertes point bas du prévisionnel : critique sous 0 €, vigilance sous 5 000 €, OK au-dessus.
- Harmonisation des tableaux de récurrences : alternance des lignes, sélection ligne complète, suppression du focus cellule/traits parasites.
- Ajout de fichiers de recette : faux fichier DB invalide et CSV de 500 transactions.
- Conservation des corrections V0.4.13 : revenus stricts, filtre période, à catégoriser, vue cartes/tableau, raccord Comptes → Transactions.

## V0.4.13 — Recette V0.4.12 & correctifs métier/UI
- Correction BR-008 : un revenu est désormais un montant positif explicitement catégorisé `Revenus`.
- Correction BR-009 : les dépenses courantes restent centralisées via la règle métier `is_current_expense()`.
- Correction TRX-010 : le filtre période des Transactions est désormais opérationnel.
- Correction TRX-013 : l’onglet `À catégoriser` suit la règle métier statut/catégorie.
- Correction CPT-010 : le bouton `Voir transactions` ouvre l’écran Transactions filtré sur le compte sélectionné.
- Correction CPT-008 : activation de la bascule `Vue tableau` / `Vue cartes` dans Comptes.
- Ajout d’une méthode `select_account_filter()` dans Transactions pour les raccords inter-écrans.

## V0.4.12 — Patrimoine : tableaux harmonisés
- Correction de l’affichage des lignes dans les tableaux Patrimoine.
- Le tableau `Top actifs` utilise maintenant la même règle UI que les transactions : sélection par ligne, fond doux, pas de bordure/focus noir sur les cellules.
- Les tableaux `Actifs`, `Passifs` et `Top actifs` partagent la même présentation.
- Suppression des traits parasites sur les lignes pointées ou sélectionnées.
- Alignement avec la règle UI validée précédemment : présentation homogène des tableaux de maintenance.

## V0.4.11 — Patrimoine : navigation par onglets enrichie
- Ajout de l’onglet `Synthèse intelligente`.
- Ajout de l’onglet `Top actifs`.
- Allègement de `Vue globale`, qui conserve uniquement les graphiques de synthèse immédiate.
- Suppression du besoin de dérouler l’écran Patrimoine pour accéder à la synthèse intelligente et au classement des actifs.
- Le Top actifs dispose maintenant d’un tableau dédié et d’un résumé des principaux actifs.

## V0.4.10 — Sécurisation base SQLite
- Correction de sécurité : gestion du cas `sqlite3.DatabaseError: file is not a database`.
- Au démarrage et à chaque connexion, Valoria Vision vérifie que `data/valoria_vision.db` est bien une base SQLite valide.
- Si le fichier est invalide/corrompu, il n’est pas supprimé : il est déplacé dans `data/backups/`.
- Une nouvelle base SQLite propre est recréée automatiquement.
- L’application ne doit plus planter lors de l’ouverture du Dashboard, des Comptes ou du Prévisionnel à cause d’un fichier DB invalide.

## V0.4.9 — Ajustements UI Dashboard & Comptes
- Dashboard : ajout d'une vraie échelle de temps sous la courbe.
- Synthèse rapide : espacement corrigé entre libellés et valeurs.
- Comptes : tableau harmonisé avec Transactions, focus visuel adouci, hauteur de lignes uniforme.

# Valoria Vision — Changelog

## V0.4.8 — Dashboard raccordé au réel
- Correction du Dashboard : la courbe “Trésorerie prévisionnelle — liquidités à venir” n’utilise plus de données codées en dur.
- Ajout de `Database.dashboard_forecast_chart()`.
- Ajout de `Database.default_forecast_start_date()`.
- La courbe du Dashboard est maintenant calculée depuis le moteur réel `cash_forecast()`.
- Les scénarios Optimiste, Réaliste et Prudent du Dashboard utilisent les mêmes règles que l’écran Prévisionnel.
- Le KPI “Liquidités prévisionnelles J+30” est désormais calculé depuis le moteur prévisionnel réel.
- Les alertes du Dashboard sont raccordées au point bas réel, au solde projeté et aux flux pris en compte.
- Le Dashboard applique donc les règles métier V0.4.7 : solde initial, historique des soldes, transactions et récurrences.


# Valoria Vision — Changelog

## V0.4.7 — Solde initial & historique des soldes
- Ajout des règles métier de solde initial et d’historique dans `app/services/business_rules.py`.
- Ajout des fonctions métier :
  - `balance_at_date()` ;
  - `current_balance()` ;
  - `balance_series()` ;
  - `summarize_accounts_at_date()`.
- Ajout des colonnes SQLite `initial_balance` et `initial_date` sur les comptes.
- Migration automatique : les anciens `reference_balance/reference_date` alimentent les nouveaux `initial_balance/initial_date`.
- Le solde d’un compte à une date passée est désormais calculé depuis le solde initial et les transactions jusqu’à cette date.
- Le prévisionnel par compte démarre maintenant depuis le solde réel à la date de départ choisie, et non depuis le solde actuel.
- L’écran Comptes distingue clairement :
  - solde initial ;
  - date initiale ;
  - solde actuel calculé.
- Conservation des alias `reference_balance/reference_date` pour compatibilité interne.


# Valoria Vision — Changelog

## V0.4.6 — Récurrences cohérentes
- Correction du scénario Prudent/Optimiste : les montants des récurrences ne sont plus modifiés automatiquement.
- Une récurrence saisie à -600 € reste affichée et calculée à -600 €, y compris dans le popup journalier.
- Les scénarios resteront disponibles, mais leurs effets devront être ajoutés plus tard via des règles explicites.
- Correction de l’onglet Transactions > Récurrentes : il affiche désormais les modèles de récurrences (`recurring_items`) au lieu d’un filtrage approximatif des transactions existantes.
- L’onglet Récurrentes respecte le filtre de compte bancaire et le filtre de catégorie.
- Les lignes de l’onglet Récurrentes ne sont pas intégrées aux actions groupées de transactions, car ce sont des règles de prévision et non des opérations bancaires enregistrées.


# Valoria Vision — Changelog

## V0.4.5 — Sélection comptes dynamique
- Correction du Prévisionnel : la liste “Compte bancaire” se rafraîchit depuis SQLite à chaque affichage de l’écran.
- Les comptes créés après l’ouverture de l’application apparaissent maintenant dans le sélecteur du prévisionnel.
- Le filtre conserve la sélection courante si le compte existe encore.
- Les pages appelant `refresh()` sont recalculées lors de la navigation.
- Objectif : permettre de sélectionner immédiatement un nouveau compte bancaire, par exemple BNP, après création et import d’opérations.


# Valoria Vision — Changelog

## V0.4.4 — Filtre par compte bancaire
- Ajout d’un sélecteur **Compte bancaire** dans les filtres du Prévisionnel de trésorerie.
- Le calcul de trésorerie prévisionnelle peut désormais être limité à un compte bancaire précis.
- Les transactions futures et les récurrences sont filtrées selon le compte sélectionné.
- La carte de lecture de période affiche maintenant le compte sélectionné.
- Le nombre de modèles récurrents actifs s’adapte au compte filtré.

# Valoria Vision — Changelog

## V0.4.3 — Gestion des récurrences
- Ajout du bouton “Gérer les récurrences” dans l’écran Prévisionnel.
- Nouvelle fenêtre listant les récurrences par compte bancaire, avec filtre, modification et suppression.
- Ajout d’un menu contextuel sur la courbe pour gérer rapidement les récurrences du jour sélectionné.
- Ajout d’un menu contextuel dans le popup journalier pour modifier ou supprimer la récurrence sélectionnée.
- Les événements prévisionnels de type récurrence embarquent désormais leur identifiant de récurrence pour permettre les actions de maintenance.

# Valoria Vision — Changelog

## V0.4.2 — Prévisionnel quotidien interactif
- La courbe prévisionnelle affiche désormais un solde pour chaque jour de la période sélectionnée.
- Suppression des boutons redondants d’en-tête : Voir échéances, Voir récurrences, Détail courbe.
- Ajout d’un popup par journée : clic ou survol d’un point pour voir uniquement les opérations du jour.
- Le popup journalier affiche les opérations réelles et prévisionnelles de la journée pointée.
- Clarification métier :
  - modèle récurrent = règle de génération, par exemple “Loyer mensuel” ;
  - opération prévisionnelle = échéance générée par cette règle sur la période.
- La vue principale conserve uniquement la lecture globale, la courbe quotidienne et les indicateurs utiles.


# Valoria Vision — Changelog

## V0.4.1 — Prévisionnel en popups
- Correction de l’écran Prévisionnel : les listes “Échéances à venir” et “Récurrences actives” ne sont plus masquées en bas de l’écran.
- Suppression des grands tableaux inférieurs dans la vue principale.
- Ajout de boutons de consultation : “Voir échéances”, “Voir récurrences”, “Détail courbe”.
- Ajout d’un menu contextuel par clic droit sur la courbe prévisionnelle.
- Ajout d’une popup “Échéances à venir sur la période”.
- Ajout d’une popup “Récurrences actives”.
- Ajout d’une popup “Détail des variations de la courbe”, avec entrées, sorties, solde net journalier et solde cumulé.
- Objectif : libérer la vue principale et garder les informations de détail accessibles.


# Valoria Vision — Changelog

## V0.4.0 — Prévisionnel de trésorerie
- Activation de l’écran Prévisionnel.
- Ajout de la table `recurring_items` pour gérer les revenus et charges récurrentes.
- Ajout d’un moteur de projection cash à 30, 60 et 90 jours.
- Scénarios disponibles : prudent, réaliste, optimiste.
- Projection basée sur les liquidités actuelles, transactions futures et récurrences.
- Ajout des KPI prévisionnels : cash de départ, cash projeté, point bas, encaissements, décaissements.
- Ajout de la courbe de trésorerie prévisionnelle.
- Ajout de la liste des échéances à venir.
- Ajout du formulaire “Ajouter une récurrence”.


# Valoria Vision — Changelog

## V0.3.5 — Multi-sélection & actions groupées
- Ajout d'une colonne de cases à cocher sur les tableaux de transactions.
- Sélection multiple par cases à cocher.
- Sélection / désélection rapide via l'en-tête de la première colonne.
- Ajout d'une barre d'actions groupées affichée lorsqu'au moins une transaction est sélectionnée.
- Actions groupées sur transactions : modifier la catégorie, marquer validée, marquer à catégoriser, supprimer.
- Ajout d'un menu contextuel par clic droit sur le tableau Transactions.
- Ajout des méthodes SQLite groupées correspondantes.
- Périmètre prioritaire V0.3.5 : transactions.


# Valoria Vision — Changelog

## V0.3.4 — Patrimoine calculé sur données réelles
- Correction de l’écran Patrimoine : la courbe “Évolution du patrimoine net” n’utilise plus de données figées.
- Ajout de `Database.patrimonio_evolution()` pour calculer l’historique depuis `asset_values`.
- La courbe de la vue globale et l’onglet Évolution utilisent le même moteur de données.
- La répartition des actifs reste basée sur les actifs réels enregistrés en base.
- Objectif : cohérence entre les KPI Patrimoine, la répartition et l’évolution historique.


# Valoria Vision — Changelog

## V0.3.3 — Identification imports par IBAN
- L’historique des imports affiche désormais l’identifiant bancaire/IBAN du compte au lieu du seul nom de compte.
- L’identifiant est masqué au milieu pour rester lisible sans exposer toute la donnée bancaire.
- La liste de choix du compte d’import affiche aussi l’identifiant bancaire.
- Objectif : éviter toute ambiguïté lorsque plusieurs comptes portent un nom similaire.
- Périmètre métier V0.3 conservé.


# Valoria Vision — Changelog

## V0.3.2 — Correctif aperçu import
- Correction du crash `NameError: name 'row' is not defined` dans la fenêtre d’aperçu détaillé de l’import.
- Séparation propre entre l’aperçu des opérations importées et le tableau des transactions enregistrées.
- Conservation du correctif V0.3.1 : le bouton “4. Importer les opérations” lance l’import après confirmation.
- Périmètre V0.3.0 conservé sans nouvelle fonction métier.


# Valoria Vision — Changelog

## V0.3.1 — Correctif import bancaire
- Correction du bouton “4. Importer les opérations” : il lance maintenant l’import directement après confirmation.
- Le bouton “Voir l’aperçu détaillé” reste dédié à la visualisation du fichier analysé.
- Activation/désactivation explicite des boutons d’aperçu et d’import selon l’état du fichier sélectionné.
- Rafraîchissement complet de l’écran Transactions après import.
- Périmètre V0.3.0 conservé sans nouvelle fonction métier.


# Valoria Vision — Changelog

## V0.3.0 — Socle technique & métier consolidé
- Consolidation du schéma SQLite avec version de schéma.
- Ajout des tables settings et categories.
- Centralisation des règles métier dans app/services/business_rules.py.
- Ajout de l'écran Paramètres avec sauvegarde/restauration.
- Ajout manuel de transactions et suppression de transaction sélectionnée.
- Mise à jour du solde de référence depuis l'écran Comptes.
- Conservation des imports bancaires, de l'aperçu détaillé et de l'annulation des lots.
- Mise à jour de l'identité Valoria Vision sur la version V0.3.0.


# Valoria Vision — Changelog

## V0.2.12 — Renommage produit
- Renommage de l'application : CashPilot devient Valoria Vision.
- Mise à jour du titre de fenêtre.
- Mise à jour du bloc marque dans le menu latéral.
- Mise à jour des textes visibles et documents internes.
- Conservation du périmètre fonctionnel validé en V0.2.11.
- Version destinée au versionnage et aux captures LinkedIn sous la nouvelle identité.


# Valoria Vision — Changelog

## V0.2.11
- Correction du démarrage : réintégration de l'import `QGridLayout` dans l'écran Comptes.
- Conservation des volets droits activables/masquables ajoutés en V0.2.10.
- Version destinée aux captures d'écran pour la communication LinkedIn.

# V0.2.9 — Correction affichage Comptes bancaires

- Correction critique : les comptes sont de nouveau affichés dans le tableau.
- Correction technique : ajout du `setRowCount(len(rows))` avant alimentation du tableau.
- Conservation de la règle V0.2.8 : solde actuel = solde de référence + opérations postérieures à la date de référence.
- Ajout d’un filtrage effectif sur Banque, Type, Statut et Recherche.
- Le détail du compte reste cohérent avec le solde calculé.

---

## V0.2.8 — Soldes calculés après imports

- Correction du calcul du solde des comptes après import bancaire.
- Le solde affiché devient le solde actuel calculé, et non uniquement le solde de référence.
- Ajout dans le détail compte : solde actuel calculé, mouvements après référence, solde de référence.
- Les KPI Comptes et Dashboard s’appuient sur les soldes calculés.
