# V0.6.0 — Mot de passe maître & verrouillage session

## Ajouts

- Écran de création du mot de passe maître au premier lancement.
- Écran de déverrouillage aux lancements suivants.
- Hash PBKDF2-HMAC-SHA256 salé.
- Aucune conservation du mot de passe en clair.
- Bouton `Verrouiller` dans le menu latéral.
- Verrouillage automatique après inactivité.
- Diagnostic sécurité enrichi.

## Paramètres techniques

- Algorithme : PBKDF2-HMAC-SHA256
- Itérations : 390 000
- Longueur minimale : 8 caractères
- Timeout session par défaut : 10 minutes

## Limite assumée

En V0.6.0, le mot de passe protège l’accès applicatif. La dérivation directe de la clé de chiffrement depuis le mot de passe maître pourra être renforcée dans une phase ultérieure.
