"""Agents IA spécialisés de l'analyse de risques.

Chaque agent :
- produit des résultats STRUCTURÉS (modèles Pydantic) ;
- conserve les sources ;
- déclare fait / inférence / hypothèse ;
- n'invente jamais une information absente (NOT_DOCUMENTED) ;
- fait passer ses résultats par l'agent critique en fin de chaîne.
"""
