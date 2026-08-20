\# Valoria Vision — R7.2 CDC v1.1

\## Journal des modifications techniques



Branche : dev/r7.2-cdc-v1.1-imports-rapprochements  

Base stable : Valoria Vision V0.6.6-R7.2.2.1  

CDC : docs/cdc/Valoria\_Vision\_R7.2\_CDC\_correctif\_complet.pdf



\---



\## 1. Objectif



Ce journal sert à suivre toutes les modifications réalisées pendant le développement du correctif complet R7.2.



Chaque changement doit être relié :



\- à un lot du CDC ;

\- à une exigence ;

\- à un fichier modifié ;

\- à un test ou une preuve ;

\- à une décision si nécessaire.



Aucune modification métier importante ne doit rester non documentée.



\---



\## 2. Règle de tenue du journal



Pour chaque modification, renseigner :



| Champ | Description |

|---|---|

| Date | Date de la modification |

| Lot | Lot CDC concerné |

| Exigence | Exigence CDC liée |

| Fichier modifié | Fichier ou dossier concerné |

| Nature | Création / modification / suppression / migration / test |

| Résumé | Description courte du changement |

| Test associé | REC ou test technique associé |

| Résultat | Non testé / OK / KO / À reprendre |

| Commentaire | Information complémentaire |



\---



\## 3. Journal



| Date | Lot | Exigence | Fichier modifié | Nature | Résumé | Test associé | Résultat | Commentaire |

|---|---|---|---|---|---|---|---|---|

| 21/08/2026 | Lot 0 | CDC v1.1 | docs/cdc/Valoria\_Vision\_R7.2\_CDC\_correctif\_complet.pdf | Création | Ajout du CDC officiel dans le dépôt | N/A | OK | Document de référence du chantier |

| 21/08/2026 | Lot 0 | Lot 0 | docs/r7\_2/LOT\_0\_ETAT\_INITIAL.md | Création | Ajout de l’état initial et des règles de sécurisation | N/A | OK | Préparation avant développement |

| 21/08/2026 | Lot 0 | REC-01 à REC-28 | docs/r7\_2/MATRICE\_REC\_01\_A\_REC\_28.md | Création | Ajout de la matrice de recette contractuelle | REC-01 à REC-28 | Non testé | Matrice à compléter pendant le développement |

| 21/08/2026 | Lot 0 | Migration / rollback | docs/r7\_2/RAPPORT\_MIGRATION\_ROLLBACK\_R7\_2.md | Création | Ajout du rapport de migration, sauvegarde et rollback | REC-26 / REC-27 | Non testé | Contrôles à compléter pendant les lots de migration |



\---



\## 4. Fichiers sensibles à ne pas modifier sans nécessité



Les fichiers suivants ne doivent être modifiés qu’avec justification explicite :



\- app/database.py

\- app/services/forecast\_reconciliation\_service.py

\- app/ui/reconciliation\_page.py

\- app/ui/transactions\_page.py

\- app/imports/import\_service.py

\- app/imports/csv\_parser.py

\- app/imports/format\_detector.py

\- app/imports/bank\_profiles.py

\- requirements.txt

\- requirements-lock.txt

\- build\_exe.bat

\- install.bat

\- run.bat



\---



\## 5. Fichiers ou dossiers à ne jamais versionner avec des données réelles



Ne jamais ajouter volontairement au dépôt :



\- .venv/

\- data/valoria\_vision.db

\- data/secure/

\- data/security/

\- data/backups/

\- fichiers .vvdb

\- fichiers .key

\- relevés bancaires réels non anonymisés

\- exports personnels non anonymisés



\---



\## 6. Points d’attention



Points à surveiller pendant le développement R7.2 :



\- faux doublon SG #53 ;

\- contrôle du compte bancaire source ;

\- cohérence aperçu / import ;

\- audit ligne par ligne ;

\- contrôle des soldes ;

\- rollback après erreur ;

\- transactions manuelles éligibles au rapprochement ;

\- absence de double comptage prévu/réalisé ;

\- modèle de rapprochement N↔N ;

\- scoring automatique explicable ;

\- statuts Ignorée / Annulée / Remise à traiter ;

\- historique des groupes ;

\- synchronisation sans redémarrage ;

\- packaging exécutable final.



\---



\## 7. Statut du journal



Statut actuel :



```text

Initialisé — à compléter au fil des lots de développement.

