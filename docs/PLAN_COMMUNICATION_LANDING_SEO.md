# Valoria Vision - Plan communication, landing page et SEO

Date de cadrage : 2026-08-28

## Objectif

Structurer la communication publique de Valoria Vision autour d'un positionnement clair, credible et coherent avec l'etat reel du produit :

- application locale de gestion financiere personnelle ;
- suivi du cash, des comptes, des budgets, du patrimoine et du previsionnel ;
- absence de connexion bancaire permanente imposee ;
- automatisation maitrisee par imports et traitements locaux ;
- socle de base gratuit ;
- trajectoire premium pour les fonctions avancees.

Ce plan doit guider la refonte de la landing page, le referencement naturel, les publications LinkedIn et la production des futurs visuels produit.

## Positionnement a retenir

Valoria Vision n'est pas un freeware pur.

Le positionnement retenu est :

> Valoria Vision propose un socle de base gratuit pour rendre la gestion financiere personnelle accessible, avec une trajectoire premium pour les usages avances.

La communication doit donc eviter les formulations trop reductrices comme :

- "logiciel uniquement freeware" ;
- "alternative gratuite a tous les logiciels financiers" ;
- "outil complet gratuit sans limite".

Formulation recommandee :

> Valoria Vision est une application locale de gestion financiere personnelle, avec un socle de base gratuit et des fonctions premium prevues pour les besoins avances.

## Piliers de communication

| Pilier | Message |
|---|---|
| Local-first | Les donnees financieres sont traitees localement, sous le controle de l'utilisateur. |
| Sans connexion bancaire permanente | Valoria Vision n'impose pas de dependance continue a une API bancaire ou a un agregateur. |
| Automatisation maitrisee | L'objectif est d'automatiser les imports, la reconnaissance, la categorisation et le rapprochement sans automatisation opaque. |
| Socle gratuit | La version de base doit permettre un usage utile sans abonnement obligatoire des le depart. |
| Premium futur | Les fonctions avancees pourront faire partie d'une offre premium clairement identifiee. |
| Transparence produit | Le projet est encore en construction : recettage, stabilisation et refonte UI sont en cours. |

## Regles de communication

1. Ne pas presenter la nouvelle charte graphique comme deja implementee tant que l'UI R8 n'est pas livree dans l'application.
2. Les maquettes peuvent etre utilisees, mais uniquement avec une mention explicite du type : "maquette de la future interface".
3. Ne pas attaquer nommement les concurrents sur la securite.
4. Comparer les modeles d'usage, pas les acteurs : connexion permanente vs approche locale maitrisee.
5. Continuer a publier prioritairement sur LinkedIn pendant le recettage.
6. Ne pas lancer de communication massive avant un tunnel landing page -> inscription mesurable.
7. Les captures produit publiees doivent etre coherentes avec la charte validee ou clairement signalees comme anciennes/provisoires.

## Upgrade landing page

La landing page doit evoluer d'une simple page de presentation vers un mini-site de conversion et de referencement.

### Page d'accueil

Objectif : expliquer rapidement ce qu'est Valoria Vision et convertir vers la liste d'attente.

Sections recommandees :

- hero avec promesse claire ;
- benefices principaux ;
- approche locale et confidentialite ;
- automatisation maitrisee ;
- socle gratuit + premium futur ;
- apercu des modules ;
- statut du projet ;
- appel a rejoindre la liste d'attente.

Promesse recommandee :

> Une vision claire du cash, des comptes et du patrimoine, avec une application locale et maitrisee.

### Pages SEO a creer

| Page | Objectif |
|---|---|
| `/gestion-financiere-personnelle` | Positionner Valoria Vision sur la gestion financiere personnelle. |
| `/logiciel-budget-personnel-gratuit` | Clarifier le socle gratuit sans masquer la trajectoire premium. |
| `/suivi-tresorerie-personnelle` | Travailler l'axe cash et tresorerie. |
| `/gestion-patrimoine-personnel` | Travailler l'axe patrimoine. |
| `/alternative-agregateur-bancaire` | Expliquer l'approche locale sans denigrer les agregateurs. |
| `/import-csv-bancaire` | Mettre en avant l'import maitrise et les routines locales. |
| `/rapprochement-previsionnel-reel` | Expliquer le rapprochement entre transactions realisees et previsions. |
| `/journal-developpement` | Donner de la regularite, de la transparence et du contenu indexable. |
| `/beta-privee` | Convertir les visiteurs interesses en testeurs ou contacts qualifies. |

## Developpements web a prevoir

| Lot | Developpement |
|---|---|
| `LANDING-1` | Refonte du message, du hero, des CTA et des sections de preuve. |
| `SEO-1` | Titres, meta descriptions, Open Graph, sitemap, robots.txt et Search Console. |
| `SEO-2` | Creation des pages SEO thematiques et maillage interne. |
| `CONVERSION-1` | Formulaire liste d'attente avec consentement explicite et suivi des conversions. |
| `ANALYTICS-1` | Liens UTM LinkedIn, suivi visites, clics CTA et inscriptions. |
| `MEDIA-1` | Integration de visuels coherents : maquettes R8 clairement etiquetees ou captures reelles. |
| `CONTENT-1` | Journal de developpement et articles courts autour des piliers produit. |

## Developpements produit lies a la communication

| Lot | Developpement |
|---|---|
| `UI-R8-0` | Centraliser la nouvelle charte graphique dans le theme Python/PySide6. |
| `UI-R8-1` | Integrer la bibliotheque d'icones du menu lateral. |
| `UI-R8-2` | Moderniser Dashboard et Transactions comme ecrans pilotes. |
| `UI-R8-3` | Moderniser Comptes, Imports, Previsionnel, Budgets, Patrimoine et Rapprochements. |
| `DEMO-1` | Creer une base de demonstration fictive pour produire des captures propres. |
| `SCREENSHOT-1` | Prevoir un mode capture ou un jeu de donnees stable pour les visuels LinkedIn et landing page. |

## Graphiques Dashboard

La courbe de tresorerie du Dashboard ne doit pas dupliquer la courbe detaillee du module Previsionnel.

Le Dashboard doit conserver une logique de cockpit avec plusieurs lectures rapides :

- repartition des depenses du mois ;
- repartition du patrimoine ;
- flux entrants / sortants du mois ;
- alertes utiles ;
- qualite des donnees ;
- synthese rapide.

La courbe de tresorerie previsionnelle detaillee reste prioritairement rattachee au module Previsionnel.

## Sequence recommandee

### Phase 1 - Immediate

- Corriger le discours : socle gratuit + premium futur.
- Reprendre la landing page autour du positionnement local-first.
- Mettre en place le suivi UTM LinkedIn.
- Utiliser les maquettes uniquement comme "future direction graphique".
- Publier sur LinkedIn autour du parti pris produit.

### Phase 2 - Court terme

- Creer les premieres pages SEO.
- Publier le journal de developpement.
- Implementer le premier ecran pilote UI R8.
- Produire des captures reelles avec jeu de donnees fictif.

### Phase 3 - Beta privee

- Ouvrir une page beta privee plus qualifiante.
- Communiquer avec captures reelles issues de l'application.
- Distinguer clairement offre gratuite et fonctions premium envisagees.
- Mesurer les inscriptions, retours et demandes fonctionnelles.

## Decision projet

Ce plan devient une reference de cadrage pour :

- la roadmap produit ;
- la refonte de la landing page ;
- les actions SEO ;
- les publications LinkedIn ;
- la coherence visuelle entre maquettes, captures et application livree.
