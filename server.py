from __future__ import annotations

import html.parser
import json
import html
import os
import urllib.error
import urllib.parse
import urllib.request
import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("entity-graph-extractor")
SERVER_BUILD = "2026.04.20-r1"


def _compat_log2(value: float) -> float:
    if value <= 0:
        raise ValueError("math domain error")
    exponent = 0
    normalized = float(value)
    while normalized >= 2.0:
        normalized /= 2.0
        exponent += 1
    while normalized < 1.0:
        normalized *= 2.0
        exponent -= 1

    # Binary fraction approximation for log2(normalized) where normalized in [1,2).
    fraction = 0.0
    step = 0.5
    for _ in range(18):
        normalized *= normalized
        if normalized >= 2.0:
            normalized /= 2.0
            fraction += step
        step /= 2.0
    return exponent + fraction


def _compat_log(value: float, base: float = 2.718281828459045) -> float:
    if base <= 0 or base == 1:
        raise ValueError("math domain error")
    return _compat_log2(value) / _compat_log2(base)


class _MathCompat:
    @staticmethod
    def log(value: float, base: float = 2.718281828459045) -> float:
        return _compat_log(value, base)


# Keep a safe math-like object available in case any legacy code path still calls math.log.
math = _MathCompat()


STOPWORDS = {
    "A",
    "An",
    "And",
    "As",
    "At",
    "Be",
    "By",
    "For",
    "From",
    "In",
    "Into",
    "It",
    "Of",
    "On",
    "Or",
    "The",
    "To",
    "With",
}

RELATION_PATTERNS = [
    (re.compile(r"\bis a\b", re.I), "rdf:type"),
    (re.compile(r"\bis an\b", re.I), "rdf:type"),
    (re.compile(r"\bpart of\b", re.I), "schema:partOf"),
    (re.compile(r"\bworks for\b", re.I), "schema:worksFor"),
    (re.compile(r"\bfounded\b", re.I), "schema:founder"),
    (re.compile(r"\buses\b", re.I), "schema:uses"),
    (re.compile(r"\bintegrates with\b", re.I), "schema:knowsAbout"),
    (re.compile(r"\bbelongs to\b", re.I), "schema:memberOf"),
    (re.compile(r"\btargets\b", re.I), "schema:about"),
]

RELATION_RULES = [
    (re.compile(r"\bis the founder of\b", re.I), "schema:founder", "forward"),
    (re.compile(r"\bis founder of\b", re.I), "schema:founder", "forward"),
    (re.compile(r"\bfounded by\b", re.I), "schema:founder", "reverse"),
    (re.compile(r"\bfounded\b", re.I), "schema:founder", "forward"),
    (re.compile(r"\bis the author of\b", re.I), "schema:author", "forward"),
    (re.compile(r"\bis author of\b", re.I), "schema:author", "forward"),
    (re.compile(r"\bcreated by\b", re.I), "schema:creator", "reverse"),
    (re.compile(r"\bcreated\b", re.I), "schema:creator", "forward"),
    (re.compile(r"\bhas expertise in\b", re.I), "schema:knowsAbout", "forward"),
    (re.compile(r"\bspeciali[sz]es in\b", re.I), "schema:knowsAbout", "forward"),
    (re.compile(r"\bworks with\b", re.I), "schema:colleague", "forward"),
    (re.compile(r"\bworks for\b", re.I), "schema:worksFor", "forward"),
    (re.compile(r"\bis located in\b", re.I), "schema:location", "forward"),
    (re.compile(r"\blocated in\b", re.I), "schema:location", "forward"),
    (re.compile(r"\bbased in\b", re.I), "schema:location", "forward"),
    (re.compile(r"\bhas knowledge panel\b", re.I), "schema:hasKnowledgePanel", "forward"),
    (re.compile(r"\bidentified by\b", re.I), "schema:identifier", "forward"),
    (re.compile(r"\bmanufactures\b", re.I), "schema:manufactures", "forward"),
    (re.compile(r"\boperates\b", re.I), "schema:operates", "forward"),
    (re.compile(r"\bpartners with\b", re.I), "schema:partner", "forward"),
    (re.compile(r"\boffers\b", re.I), "schema:offers", "forward"),
    (re.compile(r"\bserves\b", re.I), "schema:audience", "forward"),
    (re.compile(r"\bvalued for\b", re.I), "schema:knowsAbout", "forward"),
    (re.compile(r"\bpart of\b", re.I), "schema:partOf", "forward"),
    (re.compile(r"\bintegrates with\b", re.I), "schema:knowsAbout", "forward"),
    (re.compile(r"\btargets\b", re.I), "schema:about", "forward"),
]

SITE_PROFILES = {
    "johnmingam.com": {
        "central_type": "Person",
        "expected_entities": [
            "John Mingam",
            "Méthode SFT",
            "Structure",
            "Flow",
            "Trust",
            "Universal Schema Graph",
            "LYQIO",
            "Entity SEO",
            "Knowledge Graph Google",
            "E-E-A-T",
            "Bordeaux",
            "France",
            "Wikidata",
            "Google Knowledge Panel",
        ],
        "expected_relations": [
            "schema:author",
            "schema:founder",
            "schema:knowsAbout",
            "schema:location",
            "schema:hasKnowledgePanel",
            "schema:identifier",
        ],
    },
    "apple.com": {
        "central_type": "Organization",
        "expected_entities": [
            "Apple Inc.",
            "iPhone",
            "iPad Air",
            "MacBook Pro",
            "Apple Watch",
            "AirPods Pro",
            "Apple Vision Pro",
            "AirTag",
            "Apple TV+",
            "Apple Music",
            "Apple Arcade",
            "Apple Fitness+",
            "Apple News+",
            "App Store",
            "Apple Card",
            "Apple Pay",
            "Apple Cash",
            "Apple Trade In",
            "Privacy",
            "Accessibility",
            "Environment",
            "Diversity",
        ],
        "expected_relations": [
            "schema:manufactures",
            "schema:operates",
            "schema:partner",
            "schema:offers",
            "schema:audience",
            "schema:knowsAbout",
        ],
    },
}

DEFAULT_USER_AGENT = os.environ.get(
    "ENTITY_GRAPH_USER_AGENT",
    "Entity-Graph-Extractor/1.0 (+https://example.com)",
)


class _HTMLDocumentParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_script = False
        self.in_style = False
        self.in_title = False
        self.in_heading = False
        self.in_paragraph = False
        self.in_list_item = False
        self.in_anchor = False
        self.current_link: str | None = None
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.paragraph_parts: list[str] = []
        self.anchor_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value or "" for name, value in attrs}
        if tag == "script":
            self.in_script = True
        elif tag == "style":
            self.in_style = True
        elif tag == "title":
            self.in_title = True
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.in_heading = True
        elif tag == "p":
            self.in_paragraph = True
        elif tag == "li":
            self.in_list_item = True
        elif tag == "a":
            self.in_anchor = True
            self.current_link = attributes.get("href")
        elif tag == "meta":
            name = attributes.get("name") or attributes.get("property")
            content = attributes.get("content")
            if name and content:
                self.meta[name.lower()] = content.strip()
                if name.lower() in {"description", "og:description", "og:title", "twitter:title"}:
                    self.body_parts.append(content.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.in_script = False
        elif tag == "style":
            self.in_style = False
        elif tag == "title":
            self.in_title = False
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.in_heading = False
        elif tag == "p":
            self.in_paragraph = False
        elif tag == "li":
            self.in_list_item = False
        elif tag == "a":
            self.in_anchor = False
            if self.current_link:
                self.links.append(self.current_link)
            self.current_link = None

    def handle_data(self, data: str) -> None:
        if self.in_script or self.in_style:
            return
        text = _normalize_whitespace(data)
        if not text:
            return
        self.body_parts.append(text)
        if self.in_title:
            self.title_parts.append(text)
        if self.in_heading:
            self.heading_parts.append(text)
        if self.in_paragraph or self.in_list_item:
            self.paragraph_parts.append(text)
        if self.in_anchor:
            self.anchor_parts.append(text)


def _crawl_html(source: str, *, timeout: int = 15) -> dict[str, object]:
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in {"http", "https"}:
        request = urllib.request.Request(
            source,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "")
            encoding = response.headers.get_content_charset() or "utf-8"
        html_text = payload.decode(encoding, errors="replace")
        final_url = source
    else:
        html_text = source
        final_url = ""
        content_type = "text/html"

    parser = _HTMLDocumentParser()
    parser.feed(html_text)
    parser.close()

    visible_text = _normalize_whitespace(" ".join(parser.body_parts))
    title = _normalize_whitespace(" ".join(parser.title_parts) or parser.meta.get("og:title", ""))
    headings = _normalize_whitespace(" ".join(parser.heading_parts))
    paragraphs = _normalize_whitespace(" ".join(parser.paragraph_parts))
    anchor_text = _normalize_whitespace(" ".join(parser.anchor_parts))

    return {
        "source_url": final_url,
        "content_type": content_type,
        "title": title,
        "headings": headings,
        "paragraphs": paragraphs,
        "anchor_text": anchor_text,
        "visible_text": visible_text,
        "meta": parser.meta,
        "links": parser.links,
        "raw_html": html_text,
    }


@dataclass(frozen=True)
class Triplet:
    subject: str
    predicate: str
    object: str
    evidence: str


def _entity_key(value: str) -> str:
    return _normalize_whitespace(value).lower()


def _entity_label_from_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _normalize_whitespace(value)
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        labels = [_entity_label_from_value(item) for item in value]
        return ", ".join(label for label in labels if label)
    if isinstance(value, dict):
        for key in ("name", "headline", "alternateName", "title", "legalName", "url", "@id"):
            if key in value and value[key]:
                return _entity_label_from_value(value[key])
    return _normalize_whitespace(str(value))


def _entity_type_from_label(label: str, text: str = "") -> str:
    lowered = f"{label} {text}".lower()
    if any(token in lowered for token in ["inc", "corp", "company", "organization", "store", "platform", "saas", "app store", "music", "watch", "airpods", "iphone", "ipad", "macbook", "vision pro"]):
        return "Organization" if any(token in lowered for token in ["inc", "corp", "company", "organization"]) else "Product"
    if any(token in lowered for token in ["bordeaux", "france", "paris", "london", "new york", "california"]):
        return "Place"
    if any(token in lowered for token in ["john mingam", "satoshi", "tim cook", "ceo", "founder", "author"]):
        return "Person"
    if any(token in lowered for token in ["method", "framework", "graph", "seo", "knowledge", "trust", "flow", "structure"]):
        return "Concept"
    if any(token in lowered for token in ["plugin", "tool", "extension", "software", "app"]):
        return "SoftwareApplication"
    if any(token in lowered for token in ["universal schema graph", "lyqio", "sft"]):
        return "Project"
    return "Thing"


def _load_jsonld_documents(html_text: str) -> list[dict[str, object]]:
    documents: list[dict[str, object]] = []
    for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html_text, flags=re.I | re.S):
        raw = match.group(1).strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            documents.extend(item for item in parsed if isinstance(item, dict))
        elif isinstance(parsed, dict):
            documents.append(parsed)
    return documents


def _flatten_jsonld_nodes(documents: list[dict[str, object]]) -> list[dict[str, object]]:
    nodes: list[dict[str, object]] = []
    for document in documents:
        if "@graph" in document and isinstance(document["@graph"], list):
            for node in document["@graph"]:
                if isinstance(node, dict):
                    nodes.append(node)
        else:
            nodes.append(document)
    return nodes


def _extract_jsonld_relations(html_text: str, fallback_source: str = "") -> list[Triplet]:
    documents = _flatten_jsonld_nodes(_load_jsonld_documents(html_text))
    triplets: list[Triplet] = []

    def add_triplet(subject: str, predicate: str, obj: str, evidence: str) -> None:
        subject = _normalize_whitespace(subject)
        obj = _normalize_whitespace(obj)
        if not subject or not obj:
            return
        triplets.append(Triplet(subject=subject, predicate=predicate, object=obj, evidence=evidence))

    for node in documents:
        subject = _entity_label_from_value(node)
        if not subject and fallback_source:
            subject = fallback_source
        if not subject:
            continue

        type_value = node.get("@type")
        if type_value:
            add_triplet(subject, "rdf:type", _entity_label_from_value(type_value), "json-ld")

        for key, predicate in [
            ("author", "schema:author"),
            ("creator", "schema:creator"),
            ("founder", "schema:founder"),
            ("founders", "schema:founder"),
            ("brand", "schema:brand"),
            ("manufacturer", "schema:manufactures"),
            ("offers", "schema:offers"),
            ("knowsAbout", "schema:knowsAbout"),
            ("sameAs", "schema:sameAs"),
            ("location", "schema:location"),
            ("address", "schema:address"),
            ("areaServed", "schema:areaServed"),
            ("member", "schema:member"),
            ("employee", "schema:employee"),
            ("owns", "schema:owns"),
            ("parentOrganization", "schema:parentOrganization"),
            ("subOrganization", "schema:subOrganization"),
            ("mainEntity", "schema:mainEntity"),
            ("mainEntityOfPage", "schema:mainEntityOfPage"),
            ("subjectOf", "schema:subjectOf"),
            ("hasPart", "schema:hasPart"),
            ("isPartOf", "schema:isPartOf"),
            ("url", "schema:url"),
            ("identifier", "schema:identifier"),
            ("alternateName", "schema:alternateName"),
            ("description", "schema:description"),
        ]:
            if key not in node or not node[key]:
                continue
            values = node[key] if isinstance(node[key], list) else [node[key]]
            for value in values:
                obj = _entity_label_from_value(value)
                if obj:
                    add_triplet(subject, predicate, obj, "json-ld")

    deduped: list[Triplet] = []
    seen: set[tuple[str, str, str]] = set()
    for triplet in triplets:
        key = (triplet.subject.lower(), triplet.predicate.lower(), triplet.object.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(triplet)
    return deduped


def _build_entity_nodes(entities: list[str], title: str, salience: list[dict[str, object]]) -> list[dict[str, object]]:
    salience_map = {item["entity"].lower(): item for item in salience}
    nodes: list[dict[str, object]] = []
    for entity in entities:
        item = salience_map.get(entity.lower(), {})
        nodes.append(
            {
                "id": _entity_key(entity),
                "label": entity,
                "type": _entity_type_from_label(entity, title),
                "salience": item.get("score", 0.0),
                "evidence": item.get("evidence", []),
            }
        )
    return nodes


def _select_central_entity(nodes: list[dict[str, object]], dominant_entity: str | None) -> dict[str, object] | None:
    if dominant_entity:
        for node in nodes:
            if node["label"].lower() == dominant_entity.lower():
                return node
    return nodes[0] if nodes else None


def _build_knowledge_graph(nodes: list[dict[str, object]], edges: list[dict[str, object]], profile: dict[str, object], dominant_entity: str | None) -> dict[str, object]:
    central_node = _select_central_entity(nodes, dominant_entity)
    adjacency: dict[str, list[dict[str, str]]] = {}
    for edge in edges:
        adjacency.setdefault(edge["source"], []).append({"predicate": edge["predicate"], "target": edge["target"]})
    return {
        "central_entity": central_node,
        "nodes": nodes,
        "edges": edges,
        "adjacency": adjacency,
        "profile": profile,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def _site_profile_for(source_url: str, title: str, dominant_entity: str | None, target_topic: str, entities: list[str], predicates: list[str]) -> dict[str, object]:
    host = urllib.parse.urlparse(source_url).netloc.lower()
    text_key = f"{title} {dominant_entity or ''} {target_topic}".lower()
    profile = {
        "profile_name": "generic",
        "central_type": "Thing",
        "expected_entities": [],
        "expected_relations": [],
    }

    if "apple.com" in host or "apple" in text_key:
        profile = {**SITE_PROFILES["apple.com"], "profile_name": "apple.com"}
    elif "johnmingam.com" in host or "john mingam" in text_key:
        profile = {**SITE_PROFILES["johnmingam.com"], "profile_name": "johnmingam.com"}
    elif target_topic:
        profile = {
            "profile_name": "topic-driven",
            "central_type": _entity_type_from_label(target_topic),
            "expected_entities": [target_topic] + [entity for entity in entities[:10] if entity.lower() != target_topic.lower()],
            "expected_relations": ["schema:about", "schema:knowsAbout"],
        }

    profile["observed_relations"] = sorted(set(predicates))
    return profile


def _aligned_gap_report(expected_entities: list[str], extracted_entities: list[str], expected_relations: list[str], extracted_relations: list[str]) -> dict[str, object]:
    extracted_entity_keys = {entity.lower() for entity in extracted_entities}
    extracted_relation_keys = {relation.lower() for relation in extracted_relations}
    missing_entities = [entity for entity in expected_entities if entity.lower() not in extracted_entity_keys]
    missing_relations = [relation for relation in expected_relations if relation.lower() not in extracted_relation_keys]
    entity_coverage = 1.0 if not expected_entities else round(1 - (len(missing_entities) / len(expected_entities)), 3)
    relation_coverage = 1.0 if not expected_relations else round(1 - (len(missing_relations) / len(expected_relations)), 3)
    return {
        "expected_entities": expected_entities,
        "missing_entities": missing_entities,
        "expected_relations": expected_relations,
        "missing_relations": missing_relations,
        "entity_coverage": entity_coverage,
        "relation_coverage": relation_coverage,
    }


def _build_claude_graph_brief(profile: dict[str, object], knowledge_graph: dict[str, object], gaps: dict[str, object]) -> str:
    central = knowledge_graph.get("central_entity", {}) or {}
    central_label = central.get("label", "Unknown entity")
    return (
        f"Build a knowledge graph around {central_label}. "
        f"Profile: {profile.get('profile_name', 'generic')}. "
        f"Missing entities: {', '.join(gaps.get('missing_entities', [])[:8]) or 'none'}. "
        f"Missing relations: {', '.join(gaps.get('missing_relations', [])[:8]) or 'none'}. "
        f"Use the nodes and edges to explain the page structure clearly."
    )


def _strip_html(value: str) -> str:
    value = re.sub(r"<script.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(value)


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _tokenize_words(value: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9&'\-_/\.]+", value)


def _normalize_entity(entity: str) -> str:
    entity = _normalize_whitespace(entity)
    entity = entity.strip("-_:;,.")
    if not entity:
        return entity
    if entity.isupper() and len(entity) <= 6:
        return entity
    return entity[0].upper() + entity[1:]


def _split_sentences(value: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", value)
    return [part.strip() for part in parts if part.strip()]


def _candidate_entity_phrases(value: str) -> list[str]:
    pattern = re.compile(r"\b(?:[A-Z][A-Za-z0-9&'\-_/\.]*|[A-Z]{2,})(?:\s+(?:[A-Z][A-Za-z0-9&'\-_/\.]*|[A-Z]{2,})){0,5}\b")
    candidates = []
    for match in pattern.finditer(value):
        phrase = _normalize_entity(match.group(0))
        first_word = phrase.split(" ", 1)[0]
        if first_word in STOPWORDS:
            continue
        if len(phrase) < 2:
            continue
        candidates.append(phrase)
    return candidates


def _extract_slug_entities(source_url: str) -> list[str]:
    if not source_url:
        return []
    parsed = urllib.parse.urlparse(source_url)
    tokens = [token for token in re.split(r"[-_/]+", parsed.path) if token]
    entities = []
    for token in tokens:
        cleaned = _normalize_entity(token.replace(".html", "").replace(".php", ""))
        if cleaned and len(cleaned) > 2 and cleaned.lower() not in {"index", "page", "post"}:
            entities.append(cleaned)
    return entities


def _merge_entities(candidates: Iterable[str]) -> list[str]:
    seen = set()
    ordered: list[str] = []
    for candidate in candidates:
        key = candidate.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(candidate)
    return ordered


def _collect_domain_specific_entities(text: str) -> list[str]:
    candidates: list[str] = []

    acronym_pattern = re.compile(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)?\b")
    for match in acronym_pattern.findall(text):
        candidates.append(match)

    title_pattern = re.compile(r"\b(?:[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+){1,5})\b")
    for match in title_pattern.findall(text):
        candidates.append(_normalize_entity(match))

    enumerated_pattern = re.compile(r"\b(?:[A-Z][a-z]+\s+(?:for|of|in|with)\s+[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\b")
    for match in enumerated_pattern.findall(text):
        candidates.append(_normalize_entity(match))

    return candidates


def _entity_positions(text: str, entities: list[str]) -> dict[str, int]:
    positions: dict[str, int] = {}
    lowered = text.lower()
    for entity in entities:
        index = lowered.find(entity.lower())
        if index >= 0:
            positions[entity] = index
    return positions


def _score_entities(text: str, title: str, entities: list[str]) -> list[dict[str, object]]:
    positions = _entity_positions(text, entities)
    counts = Counter(entity.lower() for entity in entities)
    max_count = max(counts.values(), default=1)
    title_lower = title.lower()
    first_window = text[:1200].lower()
    heading_window = title_lower + " " + first_window
    scores = []
    for entity in entities:
        count_score = counts[entity.lower()] / max_count
        position = positions.get(entity, len(text))
        position_score = 1.0 - min(position / max(len(text), 1), 1.0)
        title_bonus = 0.2 if entity.lower() in title_lower else 0.0
        opening_bonus = 0.12 if entity.lower() in first_window else 0.0
        heading_bonus = 0.08 if entity.lower() in heading_window else 0.0
        repetition_bonus = min(0.18, ((counts[entity.lower()] + 1) ** 0.5) * 0.06)
        phrase_bonus = 0.0
        if len(entity.split()) >= 2:
            phrase_bonus = 0.05
        score = min(1.0, round((count_score * 0.3) + (position_score * 0.22) + title_bonus + opening_bonus + heading_bonus + repetition_bonus + phrase_bonus, 3))
        evidence = []
        if entity.lower() in title_lower:
            evidence.append("title")
        if entity.lower() in first_window:
            evidence.append("opening passage")
        if entity.lower() in heading_window:
            evidence.append("heading context")
        scores.append({"entity": entity, "score": score, "evidence": evidence})
    scores.sort(key=lambda item: (item["score"], len(item["entity"])) , reverse=True)
    return scores


def _extract_triplets(sentences: list[str], entities: list[str]) -> list[Triplet]:
    triplets: list[Triplet] = []
    for sentence in sentences:
        sentence_lower = sentence.lower()
        for pattern, predicate in RELATION_PATTERNS:
            if not pattern.search(sentence_lower):
                continue
            matches = []
            for entity in entities:
                position = sentence_lower.find(entity.lower())
                if position >= 0:
                    matches.append((position, entity))
            matches.sort()
            if len(matches) >= 2:
                subject = matches[0][1]
                obj = matches[1][1]
                triplets.append(Triplet(subject=subject, predicate=predicate, object=obj, evidence=sentence))
                break
            if len(matches) == 1:
                entity = matches[0][1]
                relation_target = sentence[pattern.search(sentence_lower).start():].strip()
                triplets.append(Triplet(subject=entity, predicate=predicate, object=relation_target, evidence=sentence))
                break
        for pattern, predicate, direction in RELATION_RULES:
            match = pattern.search(sentence_lower)
            if not match:
                continue
            cue_start, cue_end = match.span()
            before = [(sentence_lower.rfind(entity.lower(), 0, cue_start), entity) for entity in entities if sentence_lower.rfind(entity.lower(), 0, cue_start) >= 0]
            after = [(sentence_lower.find(entity.lower(), cue_end), entity) for entity in entities if sentence_lower.find(entity.lower(), cue_end) >= 0]
            before.sort()
            after.sort()
            subject = None
            obj = None
            if direction == "forward":
                subject = before[-1][1] if before else None
                obj = after[0][1] if after else None
            else:
                subject = after[0][1] if after else None
                obj = before[-1][1] if before else None
            if subject and obj and subject.lower() != obj.lower():
                triplets.append(Triplet(subject=subject, predicate=predicate, object=obj, evidence=sentence))
            elif subject and not obj:
                tail = _normalize_whitespace(sentence[cue_end:])
                if tail:
                    triplets.append(Triplet(subject=subject, predicate=predicate, object=tail, evidence=sentence))
    deduped: list[Triplet] = []
    seen = set()
    for triplet in triplets:
        key = (triplet.subject.lower(), triplet.predicate.lower(), triplet.object.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(triplet)
    return deduped


def _detect_schema_candidates(text: str, title: str, dominant_entity: str | None) -> list[str]:
    haystack = f"{title} {text}".lower()
    candidates = []
    mapping = [
        ("faq", "FAQPage"),
        ("how to", "HowTo"),
        ("product", "Product"),
        ("service", "Service"),
        ("organization", "Organization"),
        ("company", "Organization"),
        ("article", "Article"),
        ("blog", "BlogPosting"),
        ("local", "LocalBusiness"),
        ("recipe", "Recipe"),
        ("course", "Course"),
        ("software", "SoftwareApplication"),
        ("app", "SoftwareApplication"),
    ]
    for needle, schema_type in mapping:
        if needle in haystack and schema_type not in candidates:
            candidates.append(schema_type)
    if dominant_entity and any(word in dominant_entity.lower() for word in ["brand", "company", "studio", "agency"]):
        if "Organization" not in candidates:
            candidates.append("Organization")
    if not candidates:
        candidates.append("WebPage")
    return candidates


def _build_mermaid(dominant_entity: str | None, entities: list[str], triplets: list[Triplet]) -> str:
    def node_id(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]", "_", value)

    lines = ["graph TD"]
    if dominant_entity:
        lines.append(f'  {node_id(dominant_entity)}["{dominant_entity}"]')
    for entity in entities[:12]:
        if entity == dominant_entity:
            continue
        lines.append(f'  {node_id(entity)}["{entity}"]')
    if triplets:
        for triplet in triplets[:20]:
            lines.append(f'  {node_id(triplet.subject)} -->|{triplet.predicate}| {node_id(triplet.object)}')
    elif dominant_entity:
        for entity in entities[:6]:
            if entity != dominant_entity:
                lines.append(f"  {node_id(dominant_entity)} --> {node_id(entity)}")
    return "\n".join(lines)


def _gap_report(expected_entities: list[str], extracted_entities: list[str]) -> list[str]:
    extracted = {entity.lower() for entity in extracted_entities}
    return [entity for entity in expected_entities if entity.lower() not in extracted]


def _derive_analysis_summary(dominant_entity: str | None, gaps: list[str], triplets: list[Triplet]) -> str:
    if dominant_entity is None:
        return "No dominant entity could be established from the input."
    gap_text = f" {len(gaps)} expected entities are missing." if gaps else " No obvious entity gap was detected from the provided reference list."
    triplet_text = f" {len(triplets)} RDF-style triplets were generated."
    return f"Dominant entity: {dominant_entity}.{gap_text}{triplet_text}"


def _extract_request_source(content: str, source_url: str) -> dict[str, object]:
    if source_url:
        try:
            return _crawl_html(source_url)
        except (urllib.error.URLError, TimeoutError, ValueError):
            pass
    if re.search(r"<html|<body|<head|<article|<section", content, flags=re.I):
        return _crawl_html(content)
    return {
        "source_url": source_url,
        "content_type": "text/plain",
        "title": "",
        "headings": "",
        "paragraphs": "",
        "anchor_text": "",
        "visible_text": _normalize_whitespace(content),
        "meta": {},
        "links": [],
        "raw_html": content,
    }


def _normalize_entity_list(values: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _normalize_whitespace(value)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
    return normalized


@mcp.tool()
def extract_entity_graph(
    content: str,
    source_url: str = "",
    title: str = "",
    target_topic: str = "",
    expected_entities: str = "",
) -> dict[str, object]:
    """Extract an entity-first graph from text or HTML.

    expected_entities should be a comma-separated list of reference entities.
    """

    source = _extract_request_source(content, source_url)
    extracted_title = _normalize_whitespace(str(source.get("title", "")))
    extracted_headings = _normalize_whitespace(str(source.get("headings", "")))
    extracted_paragraphs = _normalize_whitespace(str(source.get("paragraphs", "")))
    extracted_anchor_text = _normalize_whitespace(str(source.get("anchor_text", "")))
    visible_text = _normalize_whitespace(str(source.get("visible_text", "")))
    meta_text = _normalize_whitespace(" ".join(str(v) for v in source.get("meta", {}).values()))
    cleaned = _normalize_whitespace(" ".join([title, extracted_title, extracted_headings, extracted_paragraphs, extracted_anchor_text, meta_text, visible_text]))
    title = _normalize_whitespace(title)
    target_topic = _normalize_whitespace(target_topic)
    if not title:
        title = extracted_title or _normalize_whitespace(str(source.get("meta", {}).get("og:title", "")))

    sentences = _split_sentences(cleaned)
    candidates = []
    candidates.extend(_candidate_entity_phrases(f"{title} {cleaned}"))
    candidates.extend(_candidate_entity_phrases(f"{extracted_headings} {extracted_anchor_text}"))
    candidates.extend(_collect_domain_specific_entities(cleaned))
    candidates.extend(_extract_slug_entities(str(source.get("source_url", ""))))
    entities = _merge_entities(candidates)

    jsonld_triplets = _extract_jsonld_relations(str(source.get("raw_html", "")), target_topic or title or extracted_title)

    if target_topic and all(target_topic.lower() != entity.lower() for entity in entities):
        entities.insert(0, target_topic)

    if title:
        title_entities = _candidate_entity_phrases(title)
        for entity in reversed(title_entities):
            if entity.lower() not in {existing.lower() for existing in entities}:
                entities.insert(0, entity)

    if not entities:
        entities = [target_topic or "Unknown Entity"]

    salience = _score_entities(cleaned, title, entities)
    dominant_entity = salience[0]["entity"] if salience else None

    expected = [part.strip() for part in expected_entities.split(",") if part.strip()]
    textual_triplets = _extract_triplets(sentences, entities)
    merged_triplets: list[Triplet] = []
    seen_triplets: set[tuple[str, str, str]] = set()
    for triplet in textual_triplets + jsonld_triplets:
        key = (triplet.subject.lower(), triplet.predicate.lower(), triplet.object.lower())
        if key in seen_triplets:
            continue
        seen_triplets.add(key)
        merged_triplets.append(triplet)
    triplets = merged_triplets

    extracted_predicates = [triplet.predicate for triplet in triplets]
    profile = _site_profile_for(str(source.get("source_url", "")), title, dominant_entity, target_topic, entities, extracted_predicates)
    aligned_gap_report = _aligned_gap_report(
        _normalize_entity_list([*expected, *profile.get("expected_entities", [])]),
        entities,
        list(profile.get("expected_relations", [])),
        extracted_predicates,
    )
    entity_gaps = aligned_gap_report["missing_entities"]

    schema_candidates = _detect_schema_candidates(cleaned, title, dominant_entity)
    mermaid = _build_mermaid(dominant_entity, entities, triplets)

    crawl_metadata = {
        "source_url": source.get("source_url", ""),
        "content_type": source.get("content_type", ""),
        "meta": source.get("meta", {}),
        "link_count": len(source.get("links", [])),
    }

    nodes = _build_entity_nodes(entities, title, salience)
    knowledge_graph = _build_knowledge_graph(
        nodes,
        [
            {
                "source": _entity_key(triplet.subject),
                "predicate": triplet.predicate,
                "target": _entity_key(triplet.object),
                "label": triplet.object,
                "evidence": triplet.evidence,
                "confidence": 0.92 if triplet.predicate.startswith("schema:") or triplet.predicate == "rdf:type" else 0.76,
            }
            for triplet in triplets
        ],
        profile,
        dominant_entity,
    )

    return {
        "dominant_entity": dominant_entity,
        "salience": salience,
        "entity_gaps": entity_gaps,
        "gap_report": aligned_gap_report,
        "rdf_triplets": [triplet.__dict__ for triplet in triplets],
        "schema_org_candidates": schema_candidates,
        "mermaid": mermaid,
        "knowledge_graph": knowledge_graph,
        "claude_graph_brief": _build_claude_graph_brief(profile, knowledge_graph, aligned_gap_report),
        "analysis_summary": _derive_analysis_summary(dominant_entity, entity_gaps, triplets),
        "crawl_metadata": crawl_metadata,
        "server_runtime": {
            "build": SERVER_BUILD,
            "module": __name__,
            "file": __file__,
        },
        "input_profile": {
            "title": title,
            "target_topic": target_topic,
            "entity_count": len(entities),
            "sentence_count": len(sentences),
            "profile_name": profile.get("profile_name", "generic"),
        },
    }


if __name__ == "__main__":
    mcp.run()