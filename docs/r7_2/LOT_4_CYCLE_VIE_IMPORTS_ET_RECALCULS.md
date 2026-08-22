# Valoria Vision — R7.2 Lot 4
## Cycle de vie des imports et recalculs synchronisés

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`

---

## Décision de démarrage

Le Lot 3 est stabilisé côté recette ciblée : imports SG, reconnaissance compte multi-banques, rapports, UI comptes et menu contextuel sont validés.

Le Lot 4 démarre uniquement après cette stabilisation afin de ne pas rouvrir le périmètre du Lot 3.

---

## Objectif du Lot 4

Sécuriser le cycle de vie complet d’un import bancaire après son écriture en base.

Le Lot 4 couvre :

1. l’annulation contrôlée d’un lot d’import ;
2. le réimport possible après annulation ;
3. la protection contre les suppressions dangereuses ;
4. les recalculs synchronisés après import, annulation ou réimport ;
5. l’historique robuste des imports ;
6. l’audit des actions d’annulation.

---

## Principe métier

Un import bancaire ne doit jamais être une opération irréversible ou opaque.

L’utilisateur doit pouvoir comprendre :

- quel fichier a été importé ;
- sur quel compte ;
- combien de transactions ont été créées ;
- combien de doublons ont été ignorés ;
- quels rapports sont associés ;
- si le lot est actif ou annulé ;
- si l’annulation est possible ou bloquée ;
- ce que l’annulation va réellement supprimer.

---

## Partie A — Annulation contrôlée d’un import

### Comportement attendu

L’utilisateur doit pouvoir annuler un lot d’import précis.

L’annulation doit :

- identifier le lot ciblé ;
- supprimer uniquement les transactions importées par ce lot ;
- ne jamais supprimer les transactions manuelles ;
- ne jamais supprimer les transactions d’un autre lot ;
- mettre le lot au statut `Annulé` ;
- conserver une trace d’audit ;
- rafraîchir les écrans concernés.

### Cas nominal

Import initial :

```text
314 opérations importées
```

Annulation :

```text
314 transactions issues du lot supprimées
lot marqué Annulé
historique conservé
```

---

## Partie B — Réimport après annulation

Après annulation complète d’un lot, le même fichier doit pouvoir être réimporté.

### Résultat attendu

```text
Import initial : 314 nouvelles
Annulation : 314 supprimées
Réimport : 314 nouvelles
```

Ce point est essentiel pour valider que la gestion des signatures, doublons et lots reste cohérente.

---

## Partie C — Protection contre les annulations dangereuses

L’annulation doit être bloquée si les transactions importées sont déjà utilisées dans un lien métier critique.

### Blocages à prévoir

Blocage si au moins une transaction du lot est liée à :

- un rapprochement confirmé ;
- une occurrence prévisionnelle réalisée ou rapprochée ;
- un groupe de rapprochement futur ;
- toute relation métier qui empêcherait une suppression sûre.

### Message attendu

```text
Ce lot d’import contient des transactions déjà utilisées dans des traitements métier.
Pour préserver la cohérence, l’annulation directe est bloquée.
Annulez d’abord les rapprochements ou traitements liés.
```

Pour la première implémentation du Lot 4, la règle doit privilégier la sécurité : en cas de doute, bloquer plutôt que supprimer.

---

## Partie D — Recalculs synchronisés

Après import, annulation ou réimport, Valoria Vision doit recalculer et rafraîchir les éléments dépendants dans un ordre cohérent.

### Chaîne attendue

```text
Import / annulation
→ transactions
→ soldes de comptes
→ dashboard
→ prévisionnel
→ rapprochements
→ rapports
→ compteurs et filtres UI
```

### Objectif

Éviter les incohérences du type :

- transactions supprimées mais solde encore inchangé ;
- rapport visible mais historique non mis à jour ;
- compteurs différents des listes ;
- prévisionnel non rafraîchi après annulation ;
- rapprochements encore liés à des transactions supprimées.

---

## Partie E — Historique robuste des imports

L’historique des imports doit distinguer clairement :

- lot actif ;
- lot annulé ;
- lot avec erreurs ;
- lot avec doublons ;
- lot partiellement importé ;
- lot dont l’annulation est bloquée.

### Actions attendues dans l’historique

Selon le statut et la sécurité métier :

- voir le rapport ;
- ouvrir le dossier du rapport ;
- voir les transactions du lot ;
- annuler l’import ;
- voir la raison du blocage.

---

## Partie F — Audit d’annulation

Chaque annulation doit être tracée.

### Informations minimales

- identifiant du lot ;
- fichier source ;
- compte concerné ;
- date d’annulation ;
- nombre de transactions supprimées ;
- nombre de transactions bloquantes ;
- résultat : annulé / bloqué / erreur ;
- message technique ou métier.

---

## Hors périmètre du Lot 4

Le Lot 4 ne doit pas devenir le chantier complet des rapprochements N↔N.

Sont hors périmètre :

- refonte complète des rapprochements ;
- groupes N↔N avancés ;
- statuts exhaustifs prévu / réalisé ;
- correction du bouton `Gérer les récurrences` ;
- refonte du module Prévisionnel.

Ces sujets seront traités plus tard :

```text
Lot 5 — Prévisionnel / Récurrences
Lot 6 — Rapprochements prévisionnel / réalisé
```

---

## Tests Lot 4 à prévoir

1. Import SG 314 opérations.
2. Annulation du lot importé.
3. Vérifier que les 314 transactions importées disparaissent.
4. Vérifier que les transactions manuelles restent présentes.
5. Vérifier que le lot passe au statut Annulé.
6. Réimporter le même fichier SG.
7. Vérifier que les 314 opérations redeviennent nouvelles.
8. Réimporter à nouveau le même fichier sans annulation.
9. Vérifier que les 314 opérations sont doublons.
10. Vérifier que le rapport d’import reste accessible.
11. Vérifier que l’historique distingue les lots actifs et annulés.
12. Vérifier que les soldes, compteurs et listes sont cohérents après annulation.
13. Vérifier le blocage d’annulation si des transactions sont liées à un rapprochement confirmé.

---

## Critère de validation Lot 4

Le Lot 4 sera considéré validé si :

```text
import → annulation → réimport → doublons
```

fonctionne de manière fiable, traçable et sans incohérence visible dans les écrans principaux.

---

## Statut

Statut : **cadré — développement à démarrer**.
