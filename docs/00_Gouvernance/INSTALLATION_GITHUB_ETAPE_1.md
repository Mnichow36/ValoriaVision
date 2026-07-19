# Installation GitHub - Étape 1

## Objectif

Déposer le référentiel Phase 1 dans le dépôt GitHub de Valoria Vision **sans modifier le code de l'application**.

## Avant de commencer

- Ouvrir le dépôt GitHub Valoria Vision.
- Vérifier que l'on se trouve sur la branche principale utilisée par le projet.
- Garder une copie locale du ZIP Phase 1.
- Ne pas déposer de base réelle, de sauvegarde sensible ou de données bancaires.

## Procédure pas à pas

### 1. Décompresser le kit

Sur Windows :

1. Faire un clic droit sur `ValoriaVision_Phase1_Referentiel.zip`.
2. Choisir **Extraire tout**.
3. Ouvrir le dossier extrait.

### 2. Ouvrir le dépôt GitHub

1. Aller sur la page principale du dépôt Valoria Vision.
2. Cliquer sur l'onglet **Code**.
3. Vérifier que la branche affichée est bien la branche principale du projet.

### 3. Déposer les dossiers

1. Cliquer sur **Add file**.
2. Choisir **Upload files**.
3. Glisser dans la zone de dépôt :
   - le dossier `docs` ;
   - le dossier `.github` ;
   - le fichier `README.md` du kit, seulement si le dépôt n'a pas déjà un README principal important.
4. Attendre que GitHub ait terminé le chargement.

> Si le dépôt possède déjà un `README.md`, ne pas l'écraser. Déposer uniquement `docs` et `.github`, puis intégrer ultérieurement un lien vers `docs/README.md` dans le README existant.

### 4. Enregistrer la mise à jour

Dans la zone **Commit changes** :

- Message : `docs: ajout du référentiel projet Phase 1`
- Description facultative : `Ajout Product Backlog, Roadmap, guide GitHub, modèles d'issues et structure documentaire.`

Puis cliquer sur **Commit changes**.

### 5. Vérifier

Dans le dépôt, contrôler que les éléments suivants sont visibles :

```text
docs/00_Gouvernance
docs/01_Product_Backlog
docs/02_Roadmap
docs/05_Recette
.github/ISSUE_TEMPLATE
```

Ouvrir au moins un fichier PDF et un fichier Markdown pour confirmer qu'ils sont accessibles.

## Résultat attendu

- Le code n'a pas été modifié.
- La documentation Phase 1 est versionnée.
- Les modèles d'issues sont disponibles pour les prochains tickets.
- Le Product Backlog et la Roadmap sont conservés dans le dépôt.

## Étape suivante

Créer l'Epic **Gestion complète des comptes bancaires**, puis ses sub-issues à partir du fichier `Issues_GitHub_Gestion_Comptes.md`.
