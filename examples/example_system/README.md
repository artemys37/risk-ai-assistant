# Jeu de données de démonstration — Livrable 6

Système fictif à documenter (données 100 % fictives, aucune donnée
personnelle ou confidentielle réelle) :

**Application web interne d'une entreprise**

- Architecture : utilisateurs internes, application web, serveur Linux,
  base PostgreSQL, Active Directory, API interne, firewall, sauvegardes.
- Données : données utilisateurs, données RH, données applicatives.
- Accès : authentification utilisateur, accès administrateur, API interne.
- **Informations volontairement incomplètes** pour démontrer que les agents
  signalent les éléments nécessitant une validation humaine
  (`Non documenté`, `INFORMATION MANQUANTE`).

## Utilisation

```bash
uvicorn app.main:app --env-file .env
# Ouvrir http://127.0.0.1:8000 puis importer le fichier systeme.md
```

`systeme.md` est le document source à importer. Un `LLM` est requis pour
l'extraction documentaire (défaut : Ollama local, `LLM_PROVIDER=ollama`,
`LLM_BASE_URL=http://localhost:11434`).