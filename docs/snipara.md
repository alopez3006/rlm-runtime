# Snipara Integration

Snipara est une plateforme d'optimisation de contexte intelligente pour RLM Runtime. Au lieu de lire des fichiers entiers, le LLM interroge Snipara pour obtenir les sections les plus pertinentes.

## Qu'est-ce que Snipara ?

Snipara est une plateforme de gestion de documentation intelligente qui offre :

- **Recherche sémantique** - Trouvez du contenu pertinent par meaning plutôt que par mots-clés exacts
- **Contexte intelligent** - Récupérez automatiquement les sections de documentation pertinentes
- **Mémoire persistante** - Stockez et rappelez des informations entre les sessions
- **Synchronisation d'équipe** - Partagez des bonnes pratiques et des directives entre les membres de l'équipe

### Avantages clés

| Sans Snipara | Avec Snipara |
|--------------|--------------|
| Lecture de tous les fichiers (~500K tokens) | Contexte pertinent (~5K tokens) |
| Dépasse les limites de tokens | Respect du budget |
| Recherche basique par fichiers | Recherche sémantique + mots-clés |
| Pas de connaissances partagées | Bonnes pratiques de l'équipe |
| Gestion manuelle du contexte | Optimisation automatique |
| Pas de mémoire persistente | Rappel sémantique de la mémoire |

## Installation

```bash
pip install rlm-runtime[mcp]
```

Cette installation inclut les dépendances nécessaires :
- `httpx` - Client HTTP asynchrone pour l'API native
- `structlog` - Logging structuré

## Configuration

### OAuth (Recommandé)

Pas besoin de copier des clés API — authentifiez-vous via le navigateur :

```bash
snipara-mcp-login      # Ouvre le navigateur pour OAuth Device Flow
snipara-mcp-status     # Vérifie le statut d'authentification
```

Les tokens sont stockés dans `~/.snipara/tokens.json` et sont rafraîchis automatiquement.

### Clé API

Pour les utilisateurs open-source ou non-Snipara :

**Variables d'environnement :**

```bash
export SNIPARA_API_KEY=rlm_votre_cle_ici
export SNIPARA_PROJECT_SLUG=votre-projet
```

**Fichier de configuration (rlm.toml) :**

```toml
[rlm]
snipara_api_key = "rlm_votre_cle_ici"
snipara_project_slug = "votre-projet"
```

**Code :**

```python
from rlm import RLM

rlm = RLM(
    snipara_api_key="rlm_votre_cle_ici",
    snipara_project_slug="votre-projet",
)
```

### Résolution d'authentification

Les credentials sont résolus dans l'ordre suivant ; le premier trouvé est utilisé :

| Priorité | Source | Header | Notes |
|----------|--------|--------|-------|
| 1 | Tokens OAuth (`~/.snipara/tokens.json`) | `Authorization: Bearer <token>` | Via `snipara-mcp-login` |
| 2 | Variable d'environnement `SNIPARA_API_KEY` | `x-api-key: <key>` | Pour les clés API simples |
| 3 | `snipara_api_key` dans `rlm.toml` | `x-api-key: <key>` | Fallback de config statique |
| 4 | Import du package `snipara-mcp` | (géré par le package) | Compatibilité arrière uniquement |

Si aucun credential n'est disponible, les outils Snipara sont silencieux ignorés.

## Architecture

RLM accède à Snipara par **deux mécanismes** — un client HTTP natif (préféré) et le package `snipara-mcp` (fallback de compatibilité arrière) :

```
Orchestrator._register_snipara_tools()
    |
    +-- Tentative 1: Client HTTP natif (src/rlm/tools/snipara.py)
    |   SniparaClient.from_config(config)
    |       -> résout l'auth automatiquement
    |       -> retourne None quand pas de credentials trouvés
    |   get_native_snipara_tools(client, memory_enabled)
    |       -> 5 outils (Tiers 1+3) ou 9 outils (tous les tiers)
    |
    +-- Tentative 2: Package snipara-mcp (compatibilité arrière)
        from snipara_mcp.rlm_tools import get_snipara_tools
```

Le client natif envoie des payloads **JSON-RPC 2.0** à l'endpoint Snipara API à `https://api.snipara.com/mcp/{project_slug}`.

## Outils disponibles

Les outils sont organisés en trois niveaux :

### Niveau 1 — Récupération de contexte (toujours enregistré)

#### rlm_context_query

Outil principal de recherche de documentation sémantique/mots-clés/hybride.

```python
async def rlm_context_query(
    query: str,                           # Question ou sujet à rechercher
    max_tokens: int = 4000,               # Budget de tokens pour les résultats
    search_mode: str = "hybrid",          # "keyword" | "semantic" | "hybrid"
    prefer_summaries: bool = False,       # Préfère le contenu résumé
    include_metadata: bool = True,        # Inclut les métadonnées
) -> dict:
```

**Modes de recherche :**
- `keyword` - Correspondance TF-IDF rapide
- `semantic` - Similarité basée sur les embeddings
- `hybrid` - Combine les deux (défaut, meilleure qualité)

#### rlm_search

Recherche par motif regex dans toute la documentation indexée.

```python
async def rlm_search(
    pattern: str,              # Motif regex à rechercher
    max_results: int = 20,     # Nombre maximum de résultats
) -> list:
```

#### rlm_sections

Liste les sections de documentation indexées avec pagination.

```python
async def rlm_sections(
    filter: str | None = None,     # Filtre de préfixe de titre (insensible à la casse)
    limit: int = 50,               # Nombre maximum de sections (max: 500)
    offset: int = 0,               # Nombre de sections à sauter
) -> list:
```

#### rlm_read

Lit des lignes spécifiques de la documentation indexée.

```python
async def rlm_read(
    start_line: int,    # Ligne de début
    end_line: int,      # Ligne de fin
) -> str:
```

### Niveau 2 — Mémoire (activé par `memory_enabled`)

Ces outils nécessitent `memory_enabled = true` dans la config ou `RLM_MEMORY_ENABLED=true`.

#### rlm_remember

Stocke un souvenir pour rappel sémantique ultérieur.

```python
async def rlm_remember(
    content: str,                         # Contenu du souvenir
    type: str = "fact",                   # "fact" | "decision" | "learning" | "preference" | "todo" | "context"
    scope: str = "project",               # "agent" | "project" | "team" | "user"
    category: str | None = None,          # Catégorie de regroupement
    ttl_days: int | None = None,          # Jours jusqu'à expiration
    related_to: list[str] | None = None,  # IDs de souvenirs liés
    document_refs: list[str] | None = None,  # Chemins de documents référencés
) -> dict:
```

**Types de souvenirs :**
- `fact` - Un fait véridique
- `decision` - Une décision prise
- `learning` - Un apprentissage
- `preference` - Une préférence
- `todo` - Une tâche à faire
- `context` - Du contexte situationnel

**Portées de souvenirs :**
- `agent` - Spécifique à cet agent
- `project` - Pour tout le projet
- `team` - Pour toute l'équipe
- `user` - Pour l'utilisateur

#### rlm_recall

Recherche sémantiquement des souvenirs stockés.

```python
async def rlm_recall(
    query: str,                          # Requête de recherche
    limit: int = 5,                      # Nombre maximum de souvenirs
    min_relevance: float = 0.5,          # Score de pertinence minimum (0-1)
    type: str | None = None,             # Filtrer par type
    scope: str | None = None,            # Filtrer par portée
    category: str | None = None,         # Filtrer par catégorie
) -> list:
```

#### rlm_memories

Liste les souvenirs stockés avec des filtres optionnels.

```python
async def rlm_memories(
    type: str | None = None,        # Filtrer par type
    scope: str | None = None,       # Filtrer par portée
    category: str | None = None,    # Filtrer par catégorie
    search: str | None = None,      # Recherche textuelle dans le contenu
    limit: int = 20,                # Nombre maximum de souvenirs
    offset: int = 0,                # Pour pagination
) -> list:
```

#### rlm_forget

Supprime des souvenirs par ID, type, catégorie ou âge.

```python
async def rlm_forget(
    memory_id: str | None = None,      souvenir
    type # ID spécifique du: str | None = None,           # Supprimer par type
    category: str | None = None,       # Supprimer par catégorie
    older_than_days: int | None = None,  # Supprimer les souvenirs plus vieux que N jours
) -> dict:
```

### Niveau 3 — Avancé (toujours enregistré)

#### rlm_shared_context

Récupère le contexte fusionné des collections partagées.

```python
async def rlm_shared_context(
    categories: list[str] | None = None,   # "MANDATORY" | "BEST_PRACTICES" | "GUIDELINES" | "REFERENCE"
    max_tokens: int = 4000,                 # Budget de tokens maximum
    include_content: bool = True,           # Inclut le contenu fusionné
) -> dict:
```

**Catégories de collections partagées :**
- `MANDATORY` - Directives obligatoires
- `BEST_PRACTICES` - Bonnes pratiques
- `GUIDELINES` - Lignes directrices
- `REFERENCE` - Documentation de référence

## Variables d'environnement

| Variable | Purpose | Défaut |
|----------|---------|--------|
| `SNIPARA_API_KEY` | Clé API brute pour authentification | None |
| `SNIPARA_PROJECT_SLUG` | Slug du projet pour l'URL API | None |
| `RLM_SNIPARA_BASE_URL` | Surcharger l'URL de base API | `https://api.snipara.com/mcp` |
| `RLM_MEMORY_ENABLED` | Activer les outils de mémoire niveau 2 | `false` |
| `SNIPARA_TIMEOUT` | Timeout des requêtes en secondes | `30` |

## Utilisation

### Utilisation basique

```python
from rlm import RLM

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        snipara_api_key="rlm_...",
        snipara_project_slug="mon-projet",
    )

    # Le LLM utilisera automatiquement les outils Snipara
    result = await rlm.completion(
        "Comment fonctionne le système d'authentification ? "
        "Incluez des exemples de code."
    )

    print(result.response)
    print(f"Appels d'outils: {result.total_tool_calls}")
```

### Utilisation avec mémoire

```python
from rlm import RLM

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        snipara_api_key="rlm_...",
        snipara_project_slug="mon-projet",
        memory_enabled=True,  # Active les outils de mémoire
    )

    # Première session - stocker une décision
    await rlm.completion(
        "Nous avons décidé d'utiliser PostgreSQL comme base de données principale."
    )

    # Session ultérieure - la décision est rappelée
    result = await rlm.completion(
        "Quelle base de données utilisons-nous pour ce projet ?"
    )
```

### Utilisation avancée avec contexte partagé

```python
from rlm import RLM, CompletionOptions

async def main():
    rlm = RLM(
        model="gpt-4o-mini",
        snipara_api_key="rlm_...",
        snipara_project_slug="mon-projet",
    )

    # Récupérer les bonnes pratiques de l'équipe
    options = CompletionOptions(
        system="Utilisez rlm_shared_context pour trouver les directives de l'équipe."
    )
    result = await rlm.completion(
        "Quelles sont nos normes de codage pour la gestion des erreurs ?",
        options=options,
    )
```

### Utilisation directe des outils

```python
from rlm.tools.snipara import SniparaClient, get_native_snipara_tools

async def main():
    # Créer le client directement
    client = SniparaClient(
        base_url="https://api.snipara.com/mcp",
        project_slug="mon-projet",
        auth_header="Bearer ...",
    )

    # Récupérer les outils
    tools = get_native_snipara_tools(client, memory_enabled=True)

    # Utiliser directement
    context = await client.call_tool("rlm_context_query", {
        "query": "authentication flow",
        "search_mode": "hybrid",
    })

    print(context)
```

## Flux de travail typique

```
1. L'utilisateur demande : "Explique l'authentification"
   |
2. Le LLM appelle : rlm_context_query("authentication")
   |
3. Snipara retourne :
   - Sections pertinentes de auth.md
   - Extraits de code de auth.py
   - Directives de sécurité associées
   - Tout dans le budget de tokens (~5K tokens)
   |
4. Le LLM synthétise la réponse en utilisant le contexte optimisé
```

## Bonnes pratiques

### Indexer votre documentation

Assurez-vous que votre documentation de projet est indexée dans Snipara :

1. Allez sur votre projet dans le [tableau de bord](https://snipara.com/dashboard)
2. Ajoutez des sources de documentation (Git, fichiers, etc.)
3. Attendez que l'indexation soit terminée

### Utiliser le contexte partagé

Pour les bonnes pratiques à l'échelle de l'équipe :

```python
result = await rlm.completion(
    "Quelles sont nos normes de codage pour la gestion des erreurs ?",
    system="Utilisez rlm_shared_context pour trouver les directives de l'équipe."
)
```

### Activer la mémoire pour les tâches multi-étapes

```toml
[rlm]
memory_enabled = true
```

Le LLM peut alors stocker des décisions et les rappeler entre les complétions.

### Définir des budgets de tokens appropriés

```python
from rlm import RLM, CompletionOptions

rlm = RLM(snipara_api_key="...", snipara_project_slug="...")

# Pour des réponses détaillées, autorisez plus de tokens
options = CompletionOptions(token_budget=12000)
result = await rlm.completion("Vue complète de l'architecture", options=options)
```

### Utiliser le bon mode de recherche

- **hybrid** (défaut) - Meilleure qualité globale
- **keyword** - Plus rapide pour les termes exacts
- **semantic** - Meilleur pour les concepts abstraits

## CLI Snipara

### snipara-mcp-login

Authentifie l'utilisateur via OAuth Device Flow :

```bash
snipara-mcp-login
```

Ouvre automatiquement le navigateur pour l'authentification. Les tokens sont stockés dans `~/.snipara/tokens.json`.

### snipara-mcp-status

Vérifie le statut d'authentification :

```bash
snipara-mcp-status
```

Affiche :
- Si l'utilisateur est connecté
- Le projet actif
- Les credentials disponibles

### snipara-mcp-logout

Déconnecte et supprime les tokens :

```bash
snipara-mcp-logout
```

## Tableau de bord Snipara

Accédez à [snipara.com/dashboard](https://snipara.com/dashboard) pour :

- **Créer et gérer des projets** - Organisez votre documentation par projet
- **Indexez des sources** - GitHub, GitLab, fichiers locaux, URLs
- **Gérez les collections partagées** - Créez des directives d'équipe
- **Configurez les membres de l'équipe** - Partagez l'accès aux projets
- **Surveillez l'utilisation** - Suivez les requêtes et le budget

## tarification

Snipara facture par requête de contexte :

| Plan | Requêtes/Mois | Prix |
|------|---------------|------|
| Gratuit | 100 | $0 |
| Pro | 5,000 | $19/mois |
| Équipe | 20,000 | $49/mois |
| Entreprise | Illimité | Custom |

## Dépannage

### "Outils Snipara non enregistrés"

Vérifiez qu'au moins une source d'auth est configurée :

1. OAuth : Exécutez `snipara-mcp-login` et vérifiez avec `snipara-mcp-status`
2. Clé API : `echo $SNIPARA_API_KEY`
3. Config : Vérifiez `snipara_api_key` dans `rlm.toml`
4. Le slug du projet est défini : `echo $SNIPARA_PROJECT_SLUG`

### "SniparaAPIError: 401 Unauthorized"

1. Les tokens OAuth peuvent avoir expiré — exécutez `snipara-mcp-login` à nouveau
2. Vérifiez la clé API sur [snipara.com/dashboard](https://snipara.com/dashboard)
3. Vérifiez les fautes de frappe (les clés commencent par `rlm_`)
4. Assurez-vous que la clé a accès au projet spécifié

### "SniparaAPIError: Connection refused"

1. Vérifiez votre connexion internet
2. Vérifiez que `RLM_SNIPARA_BASE_URL` est correct (défaut : `https://api.snipara.com/mcp`)
3. Vérifiez les proxy/pare-feu qui bloquent

### "Aucun résultat retourné"

1. Vérifiez que votre projet a de la documentation indexée
2. Essayez une requête de recherche plus large
3. Vérifiez que le slug du projet correspond à votre tableau de bord

### Erreurs de timeout

Augmentez le timeout si nécessaire :

```bash
export SNIPARA_TIMEOUT=60
```

### Erreurs de mémoire

Si vous voyez des erreurs de mémoire :

1. Diminuez `max_tokens` dans vos requêtes
2. Activez `prefer_summaries: true`
3. Utilisez des requêtes plus spécifiques

## Intégration MCP

Snipara peut également être utilisé comme serveur MCP pour d'autres outils :

```json
{
  "mcpServers": {
    "snipara": {
      "command": "snipara-mcp",
      "args": ["--project", "mon-projet"]
    }
  }
}
```

Pour plus de détails sur l'intégration MCP, consultez la [documentation MCP](mcp-integration.md).

## Référence API

### SniparaClient

```python
from rlm.tools.snipara import SniparaClient

client = SniparaClient(
    base_url: str = "https://api.snipara.com/mcp",
    project_slug: str | None = None,
    auth_header: str | None = None,
    timeout: float = 30.0,
)
```

**Méthodes :**
- `from_config(config)` - Crée un client depuis la configuration RLM
- `call_tool(tool_name, arguments)` - Appelle un outil Snipara
- `close()` - Ferme le client HTTP

### get_native_snipara_tools

```python
from rlm.tools.snipara import get_native_snipara_tools

tools = get_native_snipara_tools(
    client: SniparaClient,
    memory_enabled: bool = False,
) -> list[Tool]
```

Retourne 5 outils sans mémoire, 9 avec mémoire.
