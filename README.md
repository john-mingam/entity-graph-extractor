<p align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&height=260&color=0:0B132B,35:1C2541,70:3A506B,100:5BC0BE&text=Entity%20Graph%20Extractor&fontColor=ffffff&fontSize=48&fontAlignY=38&desc=Glassmorphism%20SEO%20Knowledge%20Graph%20for%20Claude&descAlignY=58&animation=fadeIn" alt="Entity Graph Extractor Hero" />
</p>

<p align="center">
  <img src="https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExM3YxOWpqY2Q3OW9vd2QxZmx1eHh2aTBzMW9zbnppMmViNnBrYnJ6dyZlcD12MV9naWZzX3NlYXJjaCZjdD1n/ZVik7pBtu9dNS/giphy.gif" width="920" alt="Entity Graph Extractor Demo" />
</p>

<p align="center"><i>Demo: entity extraction, typed relations, gap report, and Mermaid graph output.</i></p>

<p align="center">
  <img alt="Claude Extension" src="https://img.shields.io/badge/Claude-Extension-101828?style=for-the-badge">
  <img alt="MCP" src="https://img.shields.io/badge/MCP-Ready-0A7EA4?style=for-the-badge">
  <img alt="SEO Entity" src="https://img.shields.io/badge/SEO-Entity--First-1E40AF?style=for-the-badge">
  <img alt="Knowledge Graph" src="https://img.shields.io/badge/Knowledge-Graph-0F766E?style=for-the-badge">
  <img alt="License" src="https://img.shields.io/badge/License-MIT-16A34A?style=for-the-badge">
</p>

<p align="center">
  <b>Entity Graph Extractor turns Claude into a graph-first semantic SEO engine.</b><br>
  HTML crawl, entity extraction, typed relations, gap reporting, and Mermaid rendering in one workflow.
</p>

---

## Product Vision

Most SEO tools read tags.
Entity Graph Extractor reads meaning and structure.

Core goals:

- identify the dominant entity,
- verify semantic context completeness,
- output an actionable knowledge graph,
- help Claude explain page structure with clarity.

---

## What The Extension Does

1. Semantic salience scoring
- Assigns a score from 0 to 1 to each entity.
- Prioritizes title, opening passage, headings, and repetition.

2. Aligned Entity Gap Detection
- Compares the page against an entity and relation reference model.
- Returns a `gap_report` with coverage and missing items.

3. Typed relations (RDF + schema)
- Extracts Subject-Predicate-Object triplets.
- Merges text-based relations with JSON-LD when available.

4. Knowledge graph output
- Returns `knowledge_graph` with nodes, edges, central_entity, and adjacency.
- Includes `claude_graph_brief` to guide clear user-facing explanations.

5. Mermaid visualization
- Automatically generates Mermaid graph code for fast visual reporting.

---

## User Flow (Simple)

### Step 1 - Choose the input source

You can analyze:

- raw text in `content`,
- HTML in `content`,
- a live URL via `source_url`.

### Step 2 - Add SEO context

Recommended:

- `target_topic`: your main topic,
- `expected_entities`: comma-separated expected entities.

### Step 3 - Run the analysis

Main tool:

| Tool | Role |
|---|---|
| `extract_entity_graph` | Crawl + entity extraction + typed relations + gaps + knowledge graph + Mermaid |

### Step 4 - Read the output

Most useful blocks:

- `dominant_entity`: detected central entity.
- `salience`: entity ranking by importance.
- `gap_report`: missing signals for stronger semantic authority.
- `rdf_triplets`: machine-readable relations.
- `knowledge_graph`: complete graph structure.
- `mermaid`: visual graph code.

---

## Example User Prompt

```text
Analyze https://example.com with extract_entity_graph.
Target topic: Entity SEO.
Expected entities: Knowledge Graph, RDF, Schema.org, Topical Authority.
Return dominant_entity, gap_report, knowledge_graph, and mermaid.
```

---

## Before / After: Keyword SEO vs Entity SEO

| Approach | Classic Keyword SEO | Entity SEO with Entity Graph Extractor |
|---|---|---|
| Analysis unit | Primary keyword | Entities + relations + context |
| Page reading | Density and repetition | Meaning graph and semantic coherence |
| Recommendations | Add keywords | Add missing entities and missing relations |
| Schema debugging | Mostly syntax checks | NLP + JSON-LD + content structure alignment |
| Editorial control | Page-by-page tuning | Cluster-level topical authority building |
| Client deliverable | Text SEO report | Visual report with Mermaid + knowledge_graph |

Practical impact:

- less ambiguity around the main entity,
- stronger semantic robustness,
- more actionable SEO decisions for content and internal linking.

---

## Use Cases

### SEO Agency

- Run semantic audits on client pages in minutes.
- Detect entity gaps before sending strategic recommendations.
- Deliver visual Mermaid outputs to simplify client validation.

### E-commerce

- Check semantic consistency across category, brand, product, and attributes.
- Detect critical missing entities on product pages.
- Align schema.org (Product, Offer, Brand) with actual page meaning.

### SaaS

- Strengthen product entity signals and use-case clarity on marketing pages.
- Structure relations between features, integrations, and target segments.
- Accelerate SEO content workflows with outputs directly usable in Claude.

---

## Output Contract

The extension returns:

- `dominant_entity`
- `salience`
- `entity_gaps`
- `gap_report`
- `rdf_triplets`
- `schema_org_candidates`
- `crawl_metadata`
- `knowledge_graph`
- `claude_graph_brief`
- `mermaid`
- `analysis_summary`
- `server_runtime`

---

## Project Structure

```text
Entity-Graph-Extractor/
├── bootstrap.py
├── manifest.json
├── README.md
├── requirements.txt
├── server.py
└── skills/
    └── entity-graph-extractor/
        └── SKILL.md
```

---

## Installation (Claude Extension)

1. Place the extension folder in your local environment.
2. Verify `manifest.json` and `bootstrap.py`.
3. Restart Claude to load the active build.
4. Run `extract_entity_graph` on a URL or content block.

---

## Reliability Note

If you still see a runtime error, check `server_runtime` in the response to confirm the active build.

---

## License

MIT