# Site internet Valoria Vision

Ce document décrit le site public Valoria Vision, sa structure, son mode de publication et la manière de suivre ses évolutions dans le projet GitHub Valoria Vision.

## Objectif du site

Le site `valoria-vision.fr` présente Valoria Vision comme une application locale de finances personnelles et de pilotage patrimonial.

Ses objectifs principaux sont :

- expliquer le positionnement du produit : application locale, claire, orientée maîtrise des données ;
- présenter les écrans et les modules clés ;
- renforcer la confiance autour de la sécurité locale ;
- documenter le projet via le blog et le Build in Public ;
- collecter les inscriptions à la liste d'attente ;
- améliorer progressivement la visibilité SEO.

## Accès

| Élément | Emplacement |
| --- | --- |
| Site public | `https://valoria-vision.fr` |
| Projet Sites | `valoria-vision-demo` |
| Dossier de travail Codex | `/workspace/sites/valoria-vision-demo` |
| Suivi projet GitHub | Projet GitHub `Valoria Vision - Pilotage du développement` |
| Dépôt GitHub de référence produit | `Mnichow36/ValoriaVision` |

Le code du site est actuellement versionné dans le dépôt technique Sites de ChatGPT. Le suivi fonctionnel des évolutions doit en revanche être fait dans GitHub, via des issues préfixées `[SITE]`.

## Architecture du site

| Fichier ou dossier | Rôle |
| --- | --- |
| `app/page.tsx` | Page d'accueil et signaux SEO principaux |
| `app/layout.tsx` | Métadonnées globales et structure racine |
| `app/site-ui.tsx` | Composants visuels réutilisés par les pages |
| `app/site-data.ts` | Navigation, roadmap et données des écrans produit |
| `app/blog-data.ts` | Articles du blog, mots-clés, extraits et références LinkedIn |
| `app/blog/page.tsx` | Page liste du blog |
| `app/blog/[slug]/page.tsx` | Page dynamique d'un article |
| `app/ecrans/page.tsx` | Page des maquettes d'écrans |
| `app/securite-locale/page.tsx` | Page sécurité locale |
| `app/histoire/page.tsx` | Page histoire du projet |
| `app/offre/page.tsx` | Page offre |
| `app/roadmap/page.tsx` | Page feuille de route |
| `app/inscription/page.tsx` | Page liste d'attente |
| `app/api/leads/route.ts` | API de collecte des inscriptions |
| `app/sitemap.ts` | Sitemap SEO |
| `app/robots.ts` | Fichier robots pour les moteurs |
| `public/screens/` | Maquettes produit affichées sur le site |
| `tests/rendered-html.test.mjs` | Tests de rendu, SEO, navigation, mobile et assets |

## Pages publiques

| URL | Rôle éditorial |
| --- | --- |
| `/` | Page officielle Valoria Vision, priorité SEO principale |
| `/produit` | Présentation du produit et de la promesse |
| `/ecrans` | Présentation des maquettes et des modules |
| `/securite-locale` | Argumentaire sécurité, données locales et imports maîtrisés |
| `/histoire` | Histoire du projet et démarche personnelle |
| `/offre` | Positionnement gratuit/premium |
| `/roadmap` | Étapes produit et trajectoire |
| `/blog` | Hub éditorial SEO |
| `/blog/[slug]` | Articles SEO et prolongements LinkedIn |
| `/inscription` | Liste d'attente bêta privée |

## Blog et SEO

Les articles sont centralisés dans `app/blog-data.ts`.

Chaque article doit contenir :

- un `slug` court et stable ;
- un titre clair ;
- une description SEO ;
- une catégorie ;
- une date ;
- un temps de lecture ;
- une liste de mots-clés ;
- éventuellement une référence LinkedIn ;
- des sections structurées.

Lorsqu'un article est ajouté, il est automatiquement repris par :

- la page `/blog` ;
- la route `/blog/[slug]` ;
- le sitemap `app/sitemap.ts` ;
- les tests de rendu.

## Maquettes produit

Les images affichées dans la page `Écrans` sont stockées dans `public/screens/`.

Les images actuellement utilisées sont :

| Image | Usage |
| --- | --- |
| `dashboard-final-r8.jpg` | Maquette principale du dashboard |
| `imports-bancaires-r8.jpg` | Module imports bancaires |
| `budgets-r8.jpg` | Module budgets |
| `rapprochements-r8.jpg` | Module rapprochements |

Lors du remplacement d'une maquette :

1. conserver le nom du fichier si l'usage reste identique ;
2. vérifier que l'image reste lisible sur desktop et mobile ;
3. lancer `npm test` ;
4. publier uniquement après validation visuelle si la maquette a été modifiée.

## Commandes utiles

| Commande | Usage |
| --- | --- |
| `npm run dev` | Lancer le site en local |
| `npm run build` | Construire le site |
| `npm test` | Build + tests de rendu |
| `npm run validate:artifact` | Vérifier l'artefact de publication |

## Règle de suivi dans GitHub

Toutes les évolutions du site doivent être suivies dans le projet GitHub `Valoria Vision - Pilotage du développement`.

Le format recommandé pour les issues est :

```md
[SITE][DOMAINE] Titre court de l'évolution
```

Exemples :

- `[SITE][SEO] Renforcer la page d'accueil comme résultat Google principal`
- `[SITE][MOBILE] Corriger les espacements des pages internes`
- `[SITE][BLOG] Ajouter un article sur la sécurité locale`
- `[SITE][MAQUETTES] Remplacer la capture Dashboard`
- `[SITE][UX] Agrandir les vignettes des écrans au clic`

## Colonnes GitHub recommandées

| Colonne | Utilisation pour le site |
| --- | --- |
| Backlog | Idées ou problèmes identifiés |
| À spécifier | Demande à clarifier avant développement |
| Prête à développer | Spécification suffisamment claire |
| En développement | Correction ou évolution en cours |
| Audit technique | Build, tests, responsive, SEO |
| Recette fonctionnelle | Validation visuelle ou métier par François |
| À corriger | Retour après test ou publication |
| Terminé | Version publiée et vérifiée |

## Modèle d'issue GitHub

```md
## Contexte
Décrire le problème ou l'amélioration attendue.

## Objectif
Dire ce qui doit changer sur le site.

## Pages concernées
- `/`
- `/blog`
- `/ecrans`

## Critères d'acceptation
- [ ] Le rendu est correct sur desktop.
- [ ] Le rendu est correct sur mobile portrait.
- [ ] Le rendu est correct sur mobile paysage si concerné.
- [ ] Le SEO est cohérent si la page est indexable.
- [ ] `npm test` passe.
- [ ] La version est publiée si validation donnée.

## Recette
Ajouter captures, remarques ou validation.

## Publication
Indiquer la date de publication et le lien vérifié.
```

## Workflow conseillé

1. Créer une issue GitHub avec le préfixe `[SITE]`.
2. Placer l'issue dans `Backlog` ou `À spécifier`.
3. Passer en `Prête à développer` quand le besoin est clair.
4. Développer la correction dans le dépôt Sites.
5. Lancer `npm test`.
6. Présenter les captures ou le résultat si une validation visuelle est nécessaire.
7. Publier après accord explicite.
8. Commenter l'issue GitHub avec :
   - résumé de la correction ;
   - tests effectués ;
   - lien public vérifié ;
   - date de publication.
9. Passer l'issue en `Terminé`.

## Historique récent

| Commit | Évolution |
| --- | --- |
| `5c029d2` | Renforcement SEO de la page d'accueil pour Google |
| `09955ac` | Application du thème bleu nuit sur le site |
| `cd36bce` | Compactage des pages internes |
| `2b19315` | Correction des espacements mobiles et cadrage des maquettes |
| `8a8da42` | Navigation hamburger sur écrans étroits paysage |
| `efa50db` | Correction des icônes sur les maquettes Imports et Rapprochements |
| `87f52b5` | Remplacement de la maquette Dashboard sans prénom personnel |
| `736f848` | Ajout des articles SEO inspirés LinkedIn |
| `cb2c09f` | Création du blog SEO |

## Points de vigilance

- Ne pas considérer Google comme immédiat : une correction SEO publiée peut mettre plusieurs jours ou semaines à apparaître dans les résultats.
- Ne pas publier une modification visuelle sensible sans validation préalable.
- Garder la page d'accueil comme page SEO principale sur la requête marque `Valoria Vision`.
- Maintenir la cohérence graphique bleu nuit sur toutes les pages publiques.
- Éviter les grands espaces vides et les paragraphes coupés sur mobile.
- Vérifier systématiquement les maquettes après remplacement d'image.
