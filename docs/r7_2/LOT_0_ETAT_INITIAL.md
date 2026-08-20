\# Valoria Vision — R7.2 CDC v1.1

\## Lot 0 — État initial, sauvegarde et stratégie de rollback



Date de création : 21/08/2026  

Branche de travail : dev/r7.2-cdc-v1.1-imports-rapprochements  

Base stable : main — Valoria Vision V0.6.6-R7.2.2.1



\---



\## 1. Objectif du Lot 0



Le Lot 0 prépare le développement du correctif complet R7.2 conformément au CDC v1.1.



Aucune modification fonctionnelle ne doit être réalisée avant validation de ce socle.



Objectifs :



\- conserver une base stable intacte ;

\- documenter l’état initial ;

\- préparer les jeux de test ;

\- définir la stratégie de sauvegarde ;

\- définir la stratégie de rollback ;

\- éviter toute perte ou altération de données ;

\- garantir que les lots suivants seront développés et testés dans l’ordre prévu.



\---



\## 2. Référence documentaire



CDC officiel :



\- docs/cdc/Valoria\_Vision\_R7.2\_CDC\_correctif\_complet.pdf



Version du CDC :



\- Version 1.1

\- Date : 20 août 2026

\- Périmètre : Imports → Transactions → Soldes → Prévisionnel/Récurrences → Rapprochements → Audit/UX/Synchronisation



\---



\## 3. Branche et socle de départ



Branche stable :



\- main



Branche de développement :



\- dev/r7.2-cdc-v1.1-imports-rapprochements



Socle fonctionnel de départ :



\- Valoria Vision V0.6.6-R7.2.2.1

\- Dernière base locale poussée sur GitHub avant lancement du chantier CDC complet



Règle :



\- ne jamais développer directement sur main ;

\- ne jamais écraser la version stable ;

\- tous les changements R7.2 CDC v1.1 doivent être réalisés sur la branche de développement.



\---



\## 4. Modules concernés



Modules principaux :



\- Imports bancaires ;

\- Transactions ;

\- Soldes ;

\- Prévisionnel ;

\- Récurrences ;

\- Rapprochements ;

\- Audit ;

\- Synchronisation ;

\- Packaging final.



Fichiers et dossiers à auditer avant développement :



\- app/imports/

\- app/services/

\- app/ui/

\- app/database.py

\- tools/

\- docs/

\- build\_exe.bat

\- install.bat

\- run.bat

\- requirements.txt

\- requirements-lock.txt



\---



\## 5. Jeux de référence à préparer



Jeux nécessaires pour la recette REC-01 à REC-28 :



\- CSV Société Générale réel ou anonymisé ;

\- cas #53 avec deux opérations légitimes de 7,76 € ;

\- fichier avec lignes rejetées ;

\- fichier avec erreur volontaire d’écriture ;

\- base avec transactions manuelles ;

\- base avec récurrences ;

\- base avec occurrences prévisionnelles ;

\- base avec rapprochements existants ;

\- scénarios 1↔1, 1↔N, N↔1 et N↔N ;

\- base de test migration ;

\- base de test rollback.



\---



\## 6. Sauvegarde et rollback



Avant toute migration ou correction destructive :



\- sauvegarder la base de test ;

\- travailler sur copie ;

\- documenter l’état avant/après ;

\- vérifier les volumes ;

\- vérifier les sommes ;

\- vérifier les transactions ;

\- vérifier les occurrences ;

\- vérifier les rapprochements ;

\- prévoir le retour arrière.



Aucune migration ne doit être considérée valide sans preuve de rollback.



\---



\## 7. Risques identifiés



Risques majeurs :



\- faux doublon non corrigé ;

\- perte de transactions ;

\- écart de solde inexpliqué ;

\- double comptage prévu/réalisé ;

\- rapprochement partiel ;

\- cardinalité N↔N incomplète ;

\- historique supprimé ;

\- migration non réversible ;

\- synchronisation nécessitant un redémarrage ;

\- package final non autonome.



\---



\## 8. Critère de sortie du Lot 0



Le Lot 0 est terminé lorsque :



\- le CDC est dans docs/cdc ;

\- la branche de développement existe ;

\- l’état initial est documenté ;

\- les jeux de test à préparer sont listés ;

\- la stratégie sauvegarde / rollback est définie ;

\- aucune modification métier n’a encore été réalisée.



Statut Lot 0 : À compléter

