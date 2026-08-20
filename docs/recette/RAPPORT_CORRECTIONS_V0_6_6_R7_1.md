# Valoria Vision — V0.6.6-R7.1 — Corrections recette P0

## Source de travail

Version de départ : `V0.6.6-R6.1 — Rapprochements simplifiés`.

Matrice de recette utilisée : `ValoriaVision_R7_1_Matrice_Recette_Suivi_Anomalies.xlsx`.

## Périmètre traité

Cette version traite les lots P0 du plan de correction R7.1 :

1. Transactions — modification complète des transactions.
2. Patrimoine — modification/suppression, passifs, calculs et historique.
3. Rapprochements — transactions manuelles, retards, confirmation visible.
4. Prévisionnel — événement ponctuel / une seule fois.
5. Scénarios — connexion des scénarios personnalisés au prévisionnel.
6. Règles automatiques — application manuelle et création depuis transaction.
7. Non-régression — conservation du Dashboard, Plotly, sauvegarde, sécurité locale.

## Détail des corrections

### Transactions

- ajout d'une modification complète d'une transaction existante ;
- modification possible de la date, du compte, du libellé, du montant, de la catégorie et du statut ;
- recalcul automatique du type débit/crédit ;
- recalcul des signatures et impacts indirects Dashboard/Budget/Comptes ;
- suppression sécurisée des liens de rapprochement et logs de règles lors d'une suppression.

### Patrimoine

- ajout des actions Modifier / Supprimer / Voir historique dans Actifs et Passifs ;
- création et modification de passifs correctement enregistrées avec valeur négative ;
- passifs affichés dans l'onglet Passifs ;
- historique par élément patrimonial ;
- historique global depuis la synthèse intelligente.

### Rapprochements

- les transactions manuelles sont maintenant visibles dans le volet Transactions ;
- la confirmation d'une occurrence produit un statut visible ;
- les compteurs incluent les statuts confirmés ;
- le rejet et la suppression de transaction réinitialisent les liens.

### Prévisionnel

- ajout de la fréquence `Ponctuel` pour une opération prévisionnelle unique ;
- la fréquence ponctuelle n'est pas répétée ;
- impact unique dans la courbe.

### Scénarios

- le sélecteur de scénario du Prévisionnel charge les scénarios personnalisés actifs ;
- les événements de scénario sont injectés dans la courbe de trésorerie ;
- les sorties ponctuelles, achats d'actifs, investissements, mensualités et entrées simulées impactent le cash ;
- le champ Durée est désactivé pour les événements `Une fois`.

### Règles automatiques

- ajout d'une action manuelle d'application des règles aux transactions sélectionnées ;
- ajout d'une action globale dans l'écran Règles auto ;
- création d'une règle depuis transaction conservée avec rafraîchissement immédiat.

## Tests à rejouer

Rejouer les 31 tests de l'onglet `Matrice recette R7.1`, en priorité :

- R7.1-TX-01 à TX-03 ;
- R7.1-PAT-01 à PAT-07 ;
- R7.1-RAP-01 à RAP-05 ;
- R7.1-PREV-01 à PREV-03 ;
- R7.1-SCE-01 à SCE-04 ;
- R7.1-REG-01 à REG-04 ;
- R7.1-NR-01 à NR-05.

## Règle de sortie

La version reste en recette tant que les tests P0 ne sont pas rejoués et validés.
