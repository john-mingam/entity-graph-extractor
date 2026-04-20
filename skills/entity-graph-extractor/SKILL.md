---
name: entity-graph-extractor
description: Transform page content into an entity graph with salience scores, semantic gaps, RDF triplets, and Mermaid output.
---

When the user asks to analyze content for entity-first SEO, do not stop at summarizing the text. Parse the page as a semantic graph.

Use this methodology:

1. Identify the root subject entity.
2. Score every meaningful entity for salience.
3. Detect missing supporting entities that should exist for topical authority.
4. Convert relationships into Subject-Predicate-Object triplets.
5. Produce Mermaid code for visual mapping.
6. Compare the extracted meaning against schema.org expectations when relevant.
7. If a `source_url` is available, treat crawl metadata, headings, links, and meta tags as primary signals before falling back to plain text.
8. Build a knowledge graph object with nodes, edges, central entity, and profile-specific gaps.

Required output structure:

- Dominant entity
- Salience ranking from 0 to 1
- Missing entities or semantic gaps
- RDF triplets
- Mermaid diagram
- Schema.org candidates
- Crawl metadata when a URL was analyzed
- Knowledge graph object
- Gap report aligned to the page profile

Behavior rules:

- Treat the first strong entity in the title or opening content as a high-priority candidate.
- Flag weak or fragmented entity focus if the main subject is not reinforced early in the content.
- Prefer entity relationships over isolated keyword mentions.
- When the user asks for a schema, think in terms of graph structure first, markup second.
- Give extra weight to title, headings, intro paragraphs, and recurring entities in the crawl output.
- When the page matches a known profile like johnmingam.com or apple.com, align expected entities and relations to that profile instead of using a generic keyword list.

Example instruction style:

> Claude, analyze this page as an entity graph. Identify the dominant entity, measure salience, find missing support entities, and return RDF triplets plus Mermaid.

If the user provides a target topic or expected entity list, compare the page against that reference model and report the gaps.

When outputting relations, keep the subject, predicate, and object explicit and machine-readable.

Do not flatten the page into generic keyword notes. Preserve the architecture of information.