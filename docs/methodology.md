# Méthodologie d'analyse de risques

## 1. Workflow global

```
 1. Import de la documentation
 2. Extraction documentaire           → documentation-agent
 3. Identification des actifs         → asset-agent
 4. Identification des menaces        → threat-agent
 5. Identification des vulnérabilités → vulnerability-agent
 6. Construction des scénarios         → risk-scenario-agent
 7. Évaluation Probabilité × Impact   → risk-assessment-agent
 8. Critique automatique              → critic-agent
 9. Registre des risques proposé      → statut PROPOSÉ PAR IA
10. Validation humaine                → ACCEPTER / MODIFIER / REJETER
11. Registre final                    → VALIDÉ / MODIFIÉ / REJETÉ PAR HUMAIN
```

Chaque étape est identifiable dans l'interface et journalisée.

## 2. Identification des actifs

**Entrée** : extraction de l'agent Documentation.

**Catégories** : données, applications, serveurs, postes clients, équipements
réseau, comptes, services, infrastructures cloud, secrets, certificats,
interfaces, infrastructures physiques.

**Schéma** :

```json
{
  "id": "ACT-001",
  "name": "...",
  "type": "serveur",
  "description": "...",
  "owner": "...",
  "business_value": "...",
  "source": ["DOC-001§3"]
}
```

**Règles** :
- Ne **jamais** inventer un propriétaire ou une valeur métier.
- Information absente → `Non documenté`.

## 3. Identification des menaces

**Cadre** : STRIDE lorsque pertinent + catégories de menaces + bonnes pratiques.

**Schéma** :

```json
{
  "id": "THR-001",
  "name": "...",
  "description": "...",
  "target_assets": ["ACT-001"],
  "rationale": "...",
  "evidence": ["DOC-001§5"],
  "stride_category": "Elevation of Privilege",
  "confidence": "MEDIUM",
  "evidence_type": "INFERENCE"
}
```

**Règles** :
- Chaque menace est **justifiée** (`rationale` obligatoire).
- Nature de l'affirmation déclarée : `FAIT DOCUMENTÉ` / `INFERENCE` / `HYPOTHÈSE`.

## 4. Identification des vulnérabilités

**Recherche** : mauvaises configurations, absence de contrôle, faiblesses
d'architecture, vulnérabilités connues (CVE/CWE), technologies obsolètes,
authentification, contrôle d'accès, exposition réseau.

**Statuts de certitude (obligatoires)** :

| Statut | Signification |
|---|---|
| `CONFIRMÉE` | Démontrée par la documentation ou un contrôle constaté |
| `POTENTIELLE` | Très probable au vu des éléments disponibles |
| `À VÉRIFIER` | Possible mais non démontrée — **statut par défaut** |
| `NON ÉTABLIE` | Aucun élément ne la étaye |

**Règle importante** : une vulnérabilité n'est **jamais** déclarée confirmée
uniquement parce qu'elle est possible. CVE / CWE uniquement s'ils sont
réellement connus.

## 5. Construction des scénarios

```
Actif + Menace + Vulnérabilité + Contexte = Scénario de risque
```

Exemple :

> Un attaquant externe exploite une mauvaise configuration du service exposé
> afin d'obtenir un accès non autorisé aux données sensibles.

Chaque scénario précise :
- acteur / source de menace ;
- événement redouté ;
- actif impacté ;
- vulnérabilité exploitée ;
- conséquences possibles ;
- éléments de preuve ;
- hypothèses (déclarées comme telles).

## 6. Méthode de cotation

### Échelles

**Probabilité**

| Score | Libellé |
|---|---|
| 1 | Très faible |
| 2 | Faible |
| 3 | Moyenne |
| 4 | Élevée |
| 5 | Très élevée |

**Impact**

| Score | Libellé |
|---|---|
| 1 | Très faible |
| 2 | Faible |
| 3 | Moyen |
| 4 | Élevé |
| 5 | Très élevé |

### Calcul

```
Score = Probabilité × Impact        (borne 1 à 25)
```

Exemple : Probabilité = 4, Impact = 5 → **Score = 20**.

### Règles de cotation

1. Le score est **calculé** (`app/services/risk_scoring.py`), jamais choisi
   arbitrairement — reproductible et déterministe.
2. **Aucun score sans justification** : le modèle `RiskAssessment` refuse une
   évaluation vide (`justification` obligatoire, ≥ 10 caractères).
3. Système d'affichage séparé : probabilité, impact, score, justification, sources.
4. Tranche indicative affichée : 1-4 Faible · 5-9 Modéré · 10-14 Important ·
   15-19 Élevé · 20-25 Critique (affichage uniquement, ne remplace pas le score).

## 7. Règles de validation humaine

Un risque suit obligatoirement :

```
PROPOSÉ PAR IA (PENDING)
   → vérification IA (critic-agent)
   → décision analyste : ACCEPTER | MODIFIER | REJETER
   → VALIDÉ / MODIFIÉ / REJETÉ PAR HUMAIN + entrée audit
```

L'analyste peut :
- accepter, modifier ou rejeter un risque ;
- modifier probabilité, impact, justification ;
- ajouter une information ou un commentaire ;
- demander une nouvelle analyse.

**Statuts distingués** : `PROPOSÉ PAR IA` · `VALIDÉ PAR HUMAIN` ·
`MODIFIÉ PAR HUMAIN` · `REJETÉ PAR HUMAIN`.

Toute modification est journalisée (`AuditEntry`) : identifiant du risque,
ancienne/valeur nouvelle, utilisateur, date, commentaire.

## 8. Gestion de l'incertitude et des sources

- Chaque résultat porte un **niveau de confiance estimé** (`HIGH` / `MEDIUM` /
  `LOW`) avec critères explicites (sources présentes, nature de l'affirmation) —
  ce n'est **pas** une probabilité statistique.
- Information absente → `Non documenté` ou `INFORMATION MANQUANTE`.
- Chaque affirmation importante doit pouvoir être reliée à : une **source**,
  une **justification**, ou une **hypothèse explicitement déclarée**.
- Les contradictions entre documents sont signalées et demandent une validation
  humaine.

## 9. Agent critique (obligatoire)

Avant tout registre proposé, l'agent critique vérifie :

1. **Cohérence** — scénario ↔ actif, menace pertinente, vulnérabilité démontrée,
   risque cohérent.
2. **Hallucinations** — informations sans source, technologies inventées,
   vulnérabilités non démontrées, affirmations trop certaines.
3. **Traçabilité** — source / justification / hypothèse déclarée.

Sortie :

```json
{
  "status": "PASS | REVIEW_REQUIRED | REJECT",
  "issues": [],
  "missing_information": [],
  "recommendations": []
}
```
