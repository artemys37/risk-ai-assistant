# Frontend

Interface web (FastAPI + Jinja2, Sprint 5) permettant à l'analyste de :

1. importer la documentation ;
2. lancer l'analyse et suivre les 11 étapes du workflow ;
3. consulter actifs, menaces, vulnérabilités, scénarios, cotation,
   résultats de l'agent critique ;
4. **accepter / modifier / rejeter** chaque risque (obligatoire) ;
5. afficher le registre final et le journal d'audit ;
6. exporter le registre en JSON.

## Organisation des fichiers

```
frontend/
├── templates/
│   ├── base.html        # Gabarit commun + styles
│   ├── index.html       # Import des documents
│   ├── analyses.html    # Liste des analyses persistées
│   ├── analysis.html    # Étapes, sorties des agents, registre proposé,
│   │                    #   validation humaine
│   ├── audit.html       # Journal d'audit
│   └── register.html    # Registre final
```

Les routes sont définies dans `app/web.py` ; le cycle de vie métier se trouve
dans `app/services/analysis_service.py`.