\# Valoria Vision — R7.2 CDC v1.1

\## Rapport migration, sauvegarde et rollback



Branche : dev/r7.2-cdc-v1.1-imports-rapprochements  

Base stable : Valoria Vision V0.6.6-R7.2.2.1  

CDC : docs/cdc/Valoria\_Vision\_R7.2\_CDC\_correctif\_complet.pdf



\---



\## 1. Objectif



Ce document décrit la stratégie de migration, de sauvegarde et de rollback du correctif R7.2.



Aucune migration ne doit être exécutée sur une base utilisateur réelle sans sauvegarde préalable.



\---



\## 2. Principe général



Toute opération critique doit respecter l’ordre suivant :



1\. identifier la base concernée ;

2\. créer une sauvegarde ;

3\. vérifier que la sauvegarde est lisible ;

4\. appliquer la migration sur une copie ;

5\. contrôler les volumes avant/après ;

6\. contrôler les sommes avant/après ;

7\. vérifier l’absence d’orphelins ;

8\. tester le rollback ;

9\. documenter le résultat.



\---



\## 3. Données à protéger



Les données suivantes ne doivent jamais être supprimées ou modifiées silencieusement :



\- comptes ;

\- transactions ;

\- lots d’import ;

\- lignes d’audit d’import ;

\- catégories ;

\- règles automatiques ;

\- récurrences ;

\- occurrences prévisionnelles ;

\- groupes de rapprochement ;

\- membres de groupes ;

\- historique des statuts ;

\- sauvegardes ;

\- journaux utiles au diagnostic.



\---



\## 4. Sauvegarde avant migration



Avant migration, créer une sauvegarde datée de la base SQLite.



Nom recommandé :



```text

valoria\_vision\_avant\_migration\_R7\_2\_YYYYMMDD\_HHMMSS.db

