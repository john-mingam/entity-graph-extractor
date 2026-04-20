from __future__ import annotations

import os
import subprocess
import sys


def _install_dependency(package: str) -> None:
    command = [sys.executable, "-m", "pip", "install", package]
    result = subprocess.run(command, check=False)
    if result.returncode == 0:
        return

    fallback = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--user",
        "--break-system-packages",
        package,
    ]
    subprocess.run(fallback, check=True)


def _ensure_dependencies() -> None:
    try:
        import mcp  # noqa: F401
    except ModuleNotFoundError:
        _install_dependency("mcp>=1.0.0")


def _run_self_test() -> None:
    if os.environ.get("ENTITY_GRAPH_SKIP_SELF_TEST") == "1":
        return

    import server

    if not callable(getattr(server, "extract_entity_graph", None)):
        raise RuntimeError("Entity Graph Extractor self-test failed: extract_entity_graph is not callable.")

    sample = (
        "<html><head><title>John Mingam Entity SEO</title>"
        "<meta name='description' content='Entity-first SEO and knowledge graph strategy.'></head>"
        "<body><h1>John Mingam</h1><p>John Mingam created SFT and works with Entity SEO.</p></body></html>"
    )
    result = server.extract_entity_graph(
        content=sample,
        source_url="https://johnmingam.com/entity-seo",
        title="John Mingam Entity SEO",
        target_topic="Entity SEO",
        expected_entities="John Mingam,Entity SEO,Knowledge Graph",
    )

    if not isinstance(result, dict):
        raise RuntimeError("Entity Graph Extractor self-test failed: tool did not return a dictionary.")

    required_keys = {"dominant_entity", "salience", "rdf_triplets", "mermaid"}
    missing = required_keys.difference(result)
    if missing:
        raise RuntimeError(f"Entity Graph Extractor self-test failed: missing keys {sorted(missing)}.")


def main() -> None:
    _ensure_dependencies()
    _run_self_test()
    server_path = os.path.join(os.path.dirname(__file__), "server.py")
    os.execv(sys.executable, [sys.executable, server_path])


if __name__ == "__main__":
    main()