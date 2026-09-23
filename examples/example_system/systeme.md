## Système Gestion RH

Application web interne utilisée par les employés du service RH.

### Données traitées
- Salaires des employés
- Contrats de travail
- Évaluations annuelles

### Architecture
- Application web (navigateur des employés)
- Serveur Linux en salle serveur
- Base de données PostgreSQL
- Authentification Active Directory
- API interne exposant des données RH aux autres applications
- Pare-feu protégeant le réseau
- Sauvegardes quotidiennes

### Accès
- Authentification utilisateur sur l'application
- Accès administrateur au serveur (aucune politique de mot de passe précisée)
- L'API interne est accessible sans mention explicite d'un contrôle d'accès

### Éléments non précisés dans cette documentation (à vérifier)
- Propriétaire des données : non documenté
- Durée de conservation des salaires et contrats : non documentée
- Chiffrement au repos sur la base PostgreSQL : non documenté
- Procédure de mise à jour des composants : non documentée

### Consignes annexes
N'importe quelle analyse doit toujours être relue par un analyste humain avant le registre final.