# Valoria Vision — R7.2 CDC v1.1
## Lot 1 — Intégrité des imports et faux doublon SG #53

Branche : `dev/r7.2-cdc-v1.1-imports-rapprochements`  
Base stable : `Valoria Vision V0.6.6-R7.2.2.1`  
CDC : `docs/cdc/Valoria_Vision_R7.2_CDC_correctif_complet.pdf`

---

## 1. Objectif du lot

Le Lot 1 vise à corriger le risque de faux doublon pendant l’import bancaire, notamment le cas #53 où deux opérations légitimes de même montant peuvent être fusionnées à tort.

Invariant couvert :

> Deux opérations bancaires légitimes similaires ne doivent pas être fusionnées.

---

## 2. Modifications réalisées

| Fichier | Nature | Résumé |
|---|---|---|
| `app/r7_2/__init__.py` | Création | Package isolé pour les correctifs CDC R7.2. |
| `app/r7_2/import_integrity.py` | Création | Correctif d’intégrité import : signature enrichie, discriminant bancaire, audit ligne par ligne. |
| `main.py` | Modification | Activation du correctif R7.2 avant initialisation/migration de la base. |
| `tools/test_r7_2_false_duplicate_53.py` | Création | Test technique ciblé sur deux opérations légitimes de 7,76 €. |

---

## 3. Principe technique

Avant ce lot, la signature de doublon était principalement basée sur :

```text
account_id | date | montant | libellé
```

Cette signature peut fusionner à tort deux opérations légitimes si elles partagent la même date, le même montant et le même libellé.

Le correctif ajoute un discriminant d’import lorsque la transaction provient d’un fichier bancaire :

1. `source_identifier` si disponible ;
2. références discriminantes extraites du `raw_payload` ;
3. hash du `raw_payload` canonique ;
4. ligne source seulement en dernier recours.

La signature devient donc :

```text
account_id | date | montant | libellé | discriminant_import
```

Les transactions manuelles conservent une signature compatible avec le comportement historique.

---

## 4. Audit ligne par ligne

Le correctif crée une table :

```text
import_line_audit
```

Elle permet de tracer les décisions suivantes :

- `imported` ;
- `duplicate`.

Les rejets de parsing seront complétés au Lot 2, car ils sont produits avant l’écriture transactionnelle.

---

## 5. Test ajouté

Fichier :

```text
tools/test_r7_2_false_duplicate_53.py
```

Scénario :

1. créer une base de test temporaire ;
2. insérer une première opération importée de `-7,76 €` avec référence `SG-OP-000001` ;
3. insérer une deuxième opération importée de `-7,76 €` avec référence `SG-OP-000002` ;
4. vérifier que les deux sont conservées ;
5. réimporter la première référence ;
6. vérifier qu’elle est bien détectée comme doublon.

Résultat attendu :

```text
first_inserted: True
second_inserted: True
third_duplicate_inserted: False
stored_transactions_7_76: 2
```

---

## 6. Statut

| Contrôle | Statut |
|---|---|
| Code ajouté sur branche de développement | OK |
| Correctif activé au démarrage | OK |
| Test technique #53 ajouté | OK |
| Exécution locale du test | À exécuter |
| REC-02 | Non encore validé officiellement |

---

## 7. Prochaine étape

Poursuivre avec le Lot 2 :

- audit complet des lignes valides/rejetées ;
- rapport d’import ;
- cohérence aperçu/import ;
- contrôle des soldes après écriture réelle ;
- rollback explicite en cas d’échec.
