# Correctif installation R7.2.1

## Problème corrigé

L’archive R7.2 contenait `pip==...` dans `requirements-lock.txt` et le script `install.bat` lançait l’installation des dépendances avec `pip install -r requirements-lock.txt`.

Sous Windows, lorsqu’un fichier de dépendances demande aussi une modification de `pip`, pip impose d’être appelé via :

```bat
python.exe -m pip install -r requirements-lock.txt
```

Sinon l’installation s’arrête avec :

```text
ERROR: To modify pip, please run the following command:
...python.exe -m pip install -r requirements-lock.txt
```

## Correction appliquée

- `install.bat` utilise maintenant explicitement `.venv\Scripts\python.exe -m pip`.
- `pip==...` a été retiré de `requirements-lock.txt`, car `pip` n’est pas une dépendance applicative de Valoria Vision.
- Ajout de `reparer_installation_pip.bat` pour supprimer un `.venv` incomplet puis relancer l’installation proprement.

## Impact fonctionnel

Aucun changement métier R7.2.
