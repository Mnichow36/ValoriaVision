# V0.6.0 — Chiffrement base & sauvegardes

Date : 2026-07-07

## Décision technique

La V0.6.0 met en place une **enveloppe chiffrée locale** :

- vault chiffré de la base : `data/secure/valoria_vision.vvdb`
- sauvegardes chiffrées : extension `.vvb`
- chiffrement authentifié via `cryptography.Fernet`
- stockage de la clé dans le coffre OS/keyring quand disponible
- fallback développement : fichier local `data/security/valoria_local_dev.key`

## Limite assumée

Le mot de passe maître et le verrouillage de session arrivent en V0.6.0.

En V0.6.0, la base SQLite de travail reste utilisée par l’application pendant l’exécution pour préserver la compatibilité du moteur existant. Le vault chiffré et les sauvegardes chiffrées sont créés et maintenus.

## Critères d’acceptation

- une sauvegarde créée par l’application porte l’extension `.vvb` ;
- le fichier `.vvb` n’est pas ouvrable comme une base SQLite ;
- la restauration d’un `.vvb` est possible depuis Paramètres ;
- le diagnostic affiche le vault chiffré et les sauvegardes chiffrées ;
- la V0.6.0 reste obligatoire avant bêta avec données réelles.
