\# Valoria Vision — R7.2 CDC v1.1

\## Matrice de recette REC-01 à REC-28



Branche : dev/r7.2-cdc-v1.1-imports-rapprochements  

CDC : docs/cdc/Valoria\_Vision\_R7.2\_CDC\_correctif\_complet.pdf  

Base stable : Valoria Vision V0.6.6-R7.2.2.1



\---



\## Objectif



Cette matrice suit les scénarios contractuels REC-01 à REC-28 du CDC R7.2 v1.1.



Aucune exigence P0 ne doit être considérée validée sans test, preuve et résultat explicite.



\---



| ID | Scénario | Exigences liées | Résultat attendu | Statut | Preuve | Commentaire |

|---|---|---|---|---|---|---|

| REC-01 | CSV SG réel : en-tête, compte, lignes, valeurs | IMP-01, IMP-02, IMP-03, IMP-09 | Toutes les lignes sont décidées ; données conformes | Non testé | À fournir | |

| REC-02 | Faux doublon #53 : deux prélèvements légitimes de 7,76 € | IMP-04, IMP-05, IMP-06, AUD-04, SOL-03 | Deux transactions distinctes | Non testé | À fournir | |

| REC-03 | Cohérence aperçu / import | IMP-07 | Décisions et compteurs identiques | Non testé | À fournir | |

| REC-04 | Erreur pendant écriture | IMP-08 | Rollback sans état partiel | Non testé | À fournir | |

| REC-05 | Annulation de lot | IMP-11, IMP-12 | Seul le lot visé est retiré ; dépendances restaurées | Non testé | À fournir | |

| REC-06 | Rejet / doublon / erreur / ligne technique | AUD-01, AUD-02, AUD-03 | Rapport ligne, étape, motif | Non testé | À fournir | |

| REC-07 | Solde cohérent | SOL-01, SOL-02, SOL-03, SOL-04 | Écart nul à date identique | Non testé | À fournir | |

| REC-08 | Opération manquante | SOL-05, SOL-06 | Écart détecté ; non-conformité | Non testé | À fournir | |

| REC-09 | Modification non financière | TX-01, TX-02 | Montant, signe, date, compte et ID inchangés | Non testé | À fournir | |

| REC-10 | Transaction manuelle | TX-05, RAP-01 | Transaction manuelle éligible au rapprochement | Non testé | À fournir | |

| REC-11 | Filtres Transactions #54 | TX-07, TX-08 | Dates et commandes lisibles | Non testé | À fournir | |

| REC-12 | CRUD récurrences #55 | PREV-02, PREV-03 | Accès et rafraîchissement immédiats | Non testé | À fournir | |

| REC-13 | Réalisé remplace prévu | PREV-05, PREV-06 | Aucun double comptage | Non testé | À fournir | |

| REC-14 | Ignorer puis remettre à traiter #58 | STA-01, STA-02 | Retour au flux et audit | Non testé | À fournir | |

| REC-15 | Annuler occurrence #59 | STA-03, STA-04 | Hors prévisions actives ; trace conservée | Non testé | À fournir | |

| REC-16 | Rapprochement 1↔1 | RAP-03, RAP-04, RAP-05, RAP-06 | Groupe, calculs, statut, historique | Non testé | À fournir | |

| REC-17 | Rapprochement 1↔N | RAP-07 | Somme occurrences correcte | Non testé | À fournir | |

| REC-18 | Rapprochement N↔1 | RAP-08 | Somme transactions correcte | Non testé | À fournir | |

| REC-19 | Rapprochement N↔N | RAP-09, RAP-10 | Deux ensembles, totaux et écarts exacts | Non testé | À fournir | |

| REC-20 | Seuils score #57 | MAT-01 à MAT-09 | Auto / À vérifier / Aucun | Non testé | À fournir | |

| REC-21 | Contrainte dure | MAT-08 | Jamais d’auto-match incompatible | Non testé | À fournir | |

| REC-22 | Fiche métier #60 | HIS-01 à HIS-04 | Membres, score, chronologie visibles | Non testé | À fournir | |

| REC-23 | Filtres #61 | UXR-05, UXR-06 | Deux côtés retrouvables ; masquage signalé | Non testé | À fournir | |

| REC-24 | Annulation groupe | RAP-13, SYNC-03 | Membres rééligibles ; prévu restauré | Non testé | À fournir | |

| REC-25 | Synchronisation | SYNC-01 à SYNC-06 | Aucun redémarrage ; compteurs cohérents | Non testé | À fournir | |

| REC-26 | Migration historique | RAP-14, section 10.1 | Volumes, sommes et liens concordants | Non testé | À fournir | |

| REC-27 | Rollback migration | section 10.1, LIV-09 | Retour état initial démontré | Non testé | À fournir | |

| REC-28 | Traitement long | UXI-01 à UXI-03, NFR-02 | Progression réelle ; interface réactive | Non testé | À fournir | |



\---



\## Statuts autorisés



\- Non testé

\- OK

\- KO bloquant

\- KO majeur

\- KO mineur

\- À clarifier

\- N/A



\---



\## Règle de GO / NO GO



La reprise de recette générale est interdite si :



\- un P0 reste non testé ;

\- un P0 est KO ;

\- un critère NO GO du CDC est ouvert ;

\- le rollback n’est pas prouvé ;

\- une livraison ZIP autonome n’est pas testée.

