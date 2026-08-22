# Valoria Vision — R7.2 Correctifs Lot 3
## Reconnaissance compte multi-banques lors des imports

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Constat de recette

La reconnaissance actuelle du compte source fonctionne sur le fichier de test Société Générale parce que le fichier contient un identifiant exploitable, proche du numéro de compte interne.

Exemple observé : le fichier SG expose un identifiant de compte sur environ 11 caractères, alors que l'utilisateur peut renseigner dans Valoria Vision :

- un numéro de compte court ;
- un RIB partiel ou complet ;
- un IBAN complet ;
- un identifiant bancaire issu d'un autre format d'export.

Si la reconnaissance compare uniquement une valeur exacte ou une terminaison simple, elle peut échouer lorsque le compte est renseigné avec un RIB complet ou un IBAN complet.

---

## Problème métier

Valoria Vision doit pouvoir associer un fichier bancaire au bon compte même si les formats ne présentent pas l'identifiant de la même manière.

Exemples :

- fichier SG : numéro de compte court ;
- compte Valoria : IBAN complet ;
- compte Valoria : RIB complet ;
- fichier autre banque : IBAN complet ;
- fichier autre banque : numéro masqué ou partiel ;
- fichier CSV sans identifiant de compte fiable.

La reconnaissance ne doit donc pas reposer sur un champ unique `identifier` exact.

---

## Principe retenu

Mise en place du service commun :

`app/r7_2/account_resolution.py`

Ce service produit un ensemble de jetons normalisés pour chaque compte Valoria :

- numéro de compte / RIB saisi ;
- IBAN complet normalisé ;
- IBAN sans espaces ;
- chiffres extraits de l'IBAN ;
- fragments significatifs du RIB ou du BBAN ;
- suffixes longs utiles ;
- ancien champ `identifier` pour compatibilité ;
- variantes numériques sans séparateurs.

Le parser bancaire produit de son côté une liste `source_account_identifiers` à partir du fichier importé.

La correspondance compare ces deux ensembles de jetons, avec score de confiance.

---

## Règles de correspondance implémentées

### Correspondance forte

- IBAN complet fichier = IBAN complet compte ;
- RIB complet fichier = RIB complet compte ;
- numéro de compte fichier = numéro de compte compte ;
- identifiant fichier inclus de manière non ambiguë dans l'IBAN ou le RIB du compte ;
- suffixe bancaire long cohérent.

### Correspondance candidate / à confirmer

- suffixe court commun ;
- plusieurs comptes Valoria peuvent correspondre ;
- niveau de confiance insuffisant pour auto-sélection.

### Correspondance refusée

- plusieurs correspondances fortes concurrentes ;
- identifiant trop court ;
- aucun identifiant bancaire présent dans le fichier ;
- banque ou format ne permettant pas de déduire le compte source.

---

## Comportement utilisateur attendu

### Cas 1 — un seul compte reconnu avec confiance

Valoria Vision sélectionne automatiquement le compte cible et affiche une indication de cohérence :

`Compte source détecté : ... Compte cible cohérent.`

### Cas 2 — plusieurs comptes possibles

Valoria Vision bloque l'import direct et demande à l'utilisateur de sécuriser les informations de compte.

### Cas 3 — aucun compte reconnu

Valoria Vision ne doit pas inventer de correspondance.

Le message attendu est :

`Le fichier ne contient pas d'identifiant de compte reconnu ou aucun compte Valoria ne correspond. Sélectionnez ou complétez le compte cible.`

### Cas 4 — fichier sans identifiant exploitable

La sélection manuelle du compte reste possible, car l'application n'a pas de preuve de contradiction.

---

## Lien avec le parsing multi-banques

La reconnaissance compte est distincte du parsing des lignes d'opérations.

Le moteur d'import est structuré en deux niveaux :

1. `BankParserProfile` : reconnaît le format du fichier, les colonnes, les dates, les montants, les libellés et les éventuels identifiants source.
2. `account_resolution.py` : compare les identifiants trouvés dans le fichier avec les comptes Valoria.

Chaque banque peut avoir un profil spécifique, mais la résolution du compte cible utilise un service commun.

---

## Banques / formats à prévoir progressivement

Priorité R7.2 :

- Société Générale CSV réel ;
- CSV générique ;
- format à colonnes date / libellé / débit / crédit / solde si disponible.

Priorités futures :

- Boursobank / BoursoBank ;
- Crédit Agricole ;
- CIC ;
- BNP Paribas ;
- La Banque Postale ;
- Fortuneo ;
- Revolut / Wise si export CSV exploitable ;
- QIF / OFX quand le format contient des métadonnées de compte.

---

## Règle importante

L'utilisateur doit pouvoir renseigner un IBAN complet dans Valoria Vision sans casser la reconnaissance d'un fichier qui ne contient qu'un numéro de compte court.

Inversement, si le fichier contient un IBAN complet, Valoria Vision doit pouvoir reconnaître le compte même si l'utilisateur a aussi renseigné un RIB ou un numéro de compte.

---

## Tests ajoutés

Fichier :

`tools/test_r7_2_account_resolution.py`

Ce test vérifie :

- compte Valoria avec IBAN complet FR, fichier SG avec numéro court : reconnaissance forte ;
- compte Valoria avec RIB complet FR, fichier SG avec numéro court : reconnaissance forte ;
- compte Valoria avec IBAN complet étranger, fichier avec IBAN complet : reconnaissance forte ;
- deux comptes avec suffixe court proche : pas d'auto-validation ;
- compte sans identifiant : aucune correspondance ;
- génération des variantes IBAN / BBAN / suffixes.

Ce test est ajouté au script de build manuel R7.2.4 Lot 3.

---

## Statut

Statut : **développé côté branche — à vérifier dans la prochaine archive installable Lot 3**.

Décision : le Lot 3 ne sera considéré terminé qu'après recette réussie de la reconnaissance compte avec RIB complet, IBAN complet et identifiants bancaires partiels.