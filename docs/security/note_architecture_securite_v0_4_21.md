# Note architecture sécurité — V0.6.0

## Principe cible
Valoria Vision reste une application desktop locale, mais doit protéger les données financières réelles.

## Dossiers à séparer
- dossier application / code ;
- dossier utilisateur / données ;
- dossier sauvegardes ;
- dossier exports ;
- dossier logs.

## Recommandation de chemin utilisateur Windows
`%APPDATA%/ValoriaVision/` ou `%LOCALAPPDATA%/ValoriaVision/`

## Règles logs
Ne jamais écrire dans les logs :
- IBAN complet ;
- solde ;
- libellé bancaire sensible ;
- token ;
- mot de passe ;
- clé de chiffrement.

## Décision V0.6.0
Choisir entre SQLCipher, enveloppe chiffrée ou stratégie hybride temporaire.
