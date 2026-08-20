# Checklist Go / No-Go sécurité avant bêta

## Base locale
- [ ] La base `valoria_vision.db` n’est pas lisible avec un lecteur SQLite standard.
- [ ] Le mécanisme de chiffrement est documenté.
- [ ] Le chemin de stockage utilisateur est stable et documenté.

## Sauvegardes
- [ ] Les sauvegardes ne sont pas en clair.
- [ ] L’extension de sauvegarde sécurisée est définie.
- [ ] La restauration d’une sauvegarde chiffrée est testée.

## Accès application
- [ ] Un mot de passe maître est requis.
- [ ] Le hash du mot de passe n’est pas stocké en clair.
- [ ] La session peut se verrouiller.

## Données sensibles
- [ ] IBAN/identifiants masqués dans l’UI.
- [ ] Aucun solde, IBAN complet ou token dans les logs.
- [ ] Les exports futurs sont encadrés.

## Décision
- [ ] Go bêta possible.
- [ ] No-go bêta : au moins un point critique non validé.
