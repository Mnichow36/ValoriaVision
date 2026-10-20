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

## Enveloppe Tauri

En développement, Tauri démarre lui-même l’API Python sur un port local
dynamique, communique cette adresse à React par une commande native puis arrête
le processus Python à la fermeture :

```bash
cd frontend
npm run tauri dev
```

Le binaire Python autonome `valoria-engine` sera ajouté par la chaîne de
packaging Windows. En mode production, l’enveloppe refuse de démarrer si ce
binaire signé est absent.

Le mot de passe maître est vérifié exclusivement côté Python. React ne conserve
en mémoire qu’un jeton de session temporaire, jamais dans `localStorage`.
