# Interface React — prototype

Ce dossier contient le premier incrément de l’interface React de Valoria Vision.
Il ne remplace pas encore l’interface PySide.

## Démarrage

Depuis la racine du dépôt :

```bash
python -m pip install -r requirements.txt -r requirements-react-api.txt
python -m app.api.run
```

Puis, dans un second terminal :

```bash
cd frontend
npm install
npm run dev
```

L’interface est disponible sur `http://127.0.0.1:5173` et l’API sur
`http://127.0.0.1:8765`.

L’API n’initialise jamais une nouvelle base. Si aucune base utilisateur active
n’est présente, le Dashboard répond avec une erreur explicite au lieu de
réinjecter des données de démonstration.

Pour utiliser un dossier de données isolé pendant le développement :

```bash
set VALORIA_DATA_DIR=C:\chemin\vers\un\dossier\de\test
```

Ne jamais pointer le prototype vers des données personnelles pour les captures
ou les tests automatisés.
