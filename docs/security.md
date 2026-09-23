# Sécurité

> **Statut : à compléter (Sprint 6 — Sécurité).**

Ce document détaillera :

- la protection contre la **prompt injection** documentaire
  (séparation SYSTEM / USER / DOCUMENT / OUTPUT, marqueurs
  `<<<DEBUT_DOCUMENT_NON_FIABLE>>>`) ;
- la protection contre les **hallucinations** (sources, agent critique,
  statuts d'incertitude) ;
- la **gestion des secrets** (variables d'environnement, aucun `.env` en Git) ;
- la **validation des entrées** (extensions, taille maximale des fichiers) ;
- la **journalisation** des actions (audit log) ;
- le **contrôle humain** (aucune décision finale sans l'analyste) ;
- les **limites de sécurité** connues du prototype.
