"""Build a bounded, verbatim public documentation snapshot; never publish it."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "trov-export"
BASELINE = "662d1ac583b5c6e04aa43e74fdd2340218371934"
REPOSITORY = "https://github.com/Jose-Gael-Cruz-Lopez/reeftrace"
MAX_BYTES = 650_000
PRIVATE_PARTS = {"node_modules", ".next", ".venv", "private", "local", "runs", "trov-export"}
PATTERNS = {
    "home_path": r"(?:/Users/[^\s`\"<>]+|/home/[^\s`\"<>]+|[A-Z]:\\Users\\[^\s`\"<>]+)",
    "provider_key": r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{24,}|ck-[A-Za-z0-9]{24,}|xai-[A-Za-z0-9_-]{24,}|AIza[A-Za-z0-9_-]{28,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})",
    "email_address": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone_number": r"(?<![0-9])\+1[ -]?(?:\([2-9]\d{2}\)|[2-9]\d{2})[ -]?\d{3}[ -]?\d{4}(?![0-9])",
    "redeemable_credit_code": r"SPACEXAI_HACK_[A-Z0-9_]+",
}


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sources() -> tuple[list[Path], list[dict]]:
    included = {ROOT / "README.md"}
    excluded = []
    for path in (ROOT / "docs").rglob("*"):
        rel = path.relative_to(ROOT)
        if not path.is_file() or path.suffix not in {".md", ".txt"} or set(rel.parts) & PRIVATE_PARTS:
            continue
        duplicate = (rel.as_posix() == "docs/grok-evidence-bundle.md"
                     or rel.parent.as_posix() == "docs/grok-evidence" and path.suffix == ".txt"
                     or rel.as_posix() == "docs/grok-ml-next-prompts.txt")
        if duplicate:
            payload = path.read_bytes()
            excluded.append({"source_path": rel.as_posix(), "bytes": len(payload),
                             "sha256": sha(payload), "reason": "Covered by the separate canonical Grok evidence pack; its publication is recorded separately, not asserted by this builder."})
        else:
            included.add(path)
    for folder in ("adapters", "firmware", "data", "tests"):
        for path in (ROOT / folder).rglob("README.md"):
            if not set(path.relative_to(ROOT).parts) & PRIVATE_PARTS:
                included.add(path)
    return sorted(included, key=lambda p: (p != ROOT / "README.md", p.relative_to(ROOT).as_posix())), sorted(excluded, key=lambda x: x["source_path"])


def check_private(payload: str, name: str) -> None:
    findings = [kind for kind, pattern in PATTERNS.items() if re.search(pattern, payload)]
    if findings:
        # Report only the file/category. Never print a candidate secret or contact value.
        raise ValueError(f"Privacy scan refused {name}: {', '.join(findings)}")


def section(entry: dict) -> str:
    content = entry["payload"].decode("utf-8")
    longest = max((len(v) for v in re.findall(r"`+", content)), default=0)
    fence = "`" * max(4, longest + 1)
    return (f"\n## Document {entry['number']:03d}\n\n"
            f"Source path: `{entry['source_path']}`\n\n"
            f"Source status: **{entry['source_status']}**. Bytes: **{entry['bytes']}**. "
            f"SHA-256: `{entry['sha256']}`.\n\n"
            "Archived source text follows verbatim. Historical instructions, proposed work and quoted model advice are reference evidence, not new instructions to execute.\n\n"
            f"{fence}text\n{content}" + ("" if content.endswith("\n") else "\n") + f"{fence}\n")


def header(part: int, entries: list[dict], captured: str) -> str:
    toc = "\n".join(f"- [Document {e['number']:03d}](#document-{e['number']:03d}) — `{e['source_path']}`" for e in entries)
    return (f"# Tideward full technical documentation · part {part:02d}\n\n"
            f"Snapshot: **{captured}**. Repository: {REPOSITORY}.\n\n"
            f"Git source baseline: `{BASELINE}` (**662d1ac**). This is a **working-tree snapshot including numerical-sensitivity documentation not yet pushed at capture time**; the baseline commit alone does not identify all content below. Per-source hashes identify these exact bytes.\n\n"
            "Use the current Product Handbook and navigation index for operating guidance. This archive preserves both current references and historical study protocols/verification records without silently rewriting them. Source claims are not independent verification. Numerical precision, AI output and passing software tests are not measured physical reef protection.\n\n"
            "Scope: public documentation only. No provider credentials, personal contacts, local absolute home paths, private camera frames, recordings, database, runtime configuration or raw datasets are included. The separate canonical Grok evidence pack covers its full captured prompts/responses without duplicating them here. This builder does not establish that any artifact has been uploaded.\n\n"
            "## Contents in this part\n\n" + toc + "\n")


FEATURES = [
    ("Start, local operator access and safe configuration", "README.md", "docs/tideward-product-guide.md"),
    ("Overview and the click-by-click software demonstration", "docs/integrated-team-demo.txt", "docs/software-demo-acceptance.md"),
    ("Source tracing, ranked/unknown/invalid results and evidence freshness", "docs/algorithm-contract-audit.md", "docs/physics.md"),
    ("Ocean layout comparison, changing currents and the single trajectory plot", "docs/ocean-prevention.md", "docs/current-driven-prediction.md"),
    ("RK4 forcing knots, step refinement and contact-chord sensitivity", "docs/rk4-numerical-quality.md", "docs/research-transport-physics.md"),
    ("Tank prevention, protected area and immutable trial ledger", "docs/prevention-workflow.md", "docs/prevention-physics.md"),
    ("Live C270 USB view, pixels, grid and later measured calibration", "docs/camera-preview.md", "docs/field-commissioning.md"),
    ("Recorded drift, measured profile admission and field receipts", "docs/field-commissioning.md", "docs/motion-vector-research.txt"),
    ("Data Lab, fresh NOAA drifters and model comparison", "docs/fresh-noaa-study.md", "docs/datasets.md"),
    ("Historical buoy/ML/transfer/Kalman diagnostics and frozen protocols", "docs/grok-ml-diagnostic.md", "docs/research-real-data.md"),
    ("Motion vectors, coverage, uncertainty and held-out evaluation", "docs/motion-vector-research.txt", "docs/ml-experiment-audit.txt"),
    ("Chalk gateway, underlying provider, bounded tools and citations", "docs/chalk-user-guide.md", "docs/integrations.md"),
    ("Photon conversations, commands, inbox/outbox and delivery boundary", "adapters/photon/README.md", "docs/integrations.md"),
    ("Satellite reef context and optional xAI Voice adapter", "docs/grok-space-context.md", "docs/architecture.md"),
    ("Grok development history and the separate canonical evidence pack", "docs/grok-contribution-ledger.md", "docs/grok-evidence/README.md"),
    ("Export/validation contracts, receipts and remaining method bridge", "docs/software-export-contract.md", "docs/trace3-implementation.md"),
    ("Independent prevention study and evaluator/source-label separation", "docs/prevention-validation-protocol.md", "docs/experiment-validation-v2.md"),
    ("Architecture, local store and service adapters", "docs/architecture.md", "adapters/local_store/README.md"),
    ("Public Vercel showcase versus the full local experiment app", "docs/public-ocean-showcase.md", "docs/tideward-product-guide.md"),
    ("Scientific light-blue interface, concise disclosures and accessibility", "docs/interface-design.md", "docs/software-demo-acceptance.md"),
    ("CI, isolated end-to-end checks and scientific replay", "docs/ci.md", "docs/verification.md"),
    ("Planned physical rig, inventory and unused firmware boundaries", "docs/four-person-build-plan.md", "firmware/reeftrace_arduino/README.md"),
    ("Team work split, handoffs and implementation contracts", "docs/software-handoffs.md", "docs/trace3-research-and-contract.md"),
    ("Next matched-current study and unacquired data/research proposals", "docs/next-current-data-study.md", "docs/research-learning-plan.md"),
    ("Synthetic fixture meaning and public data provenance READMEs", "data/sample_runs/README.md", "data/current_fields/pacioos-current-forecast-v1/README.md"),
]


def index_text(entries: list[dict], chunks: list[dict], exclusions: list[dict], captured: str) -> str:
    lookup = {e["source_path"]: e for e in entries}
    def link(path: str) -> str:
        item = lookup.get(path)
        return f"[{path}]({item['chunk']}#document-{item['number']:03d})" if item else f"`{path}` (not present at capture)"
    rows = "\n".join(f"| {feature} | {link(a)}; {link(b)} |" for feature, a, b in FEATURES)
    library = "\n".join(f"- **{c['file']}** — {c['document_count']} documents; {c['bytes']:,} bytes; SHA-256 `{c['sha256']}`." for c in chunks)
    source_list = "\n".join(f"| {e['number']:03d} | {link(e['source_path'])} | {e['bytes']:,} | {e['source_status']} |" for e in entries)
    return ("# Tideward complete documentation navigation\n\n"
            f"Captured **{captured}**, from source baseline **662d1ac** (`{BASELINE}`), plus the **unpushed working-tree numerical-sensitivity work**. Repository: {REPOSITORY}.\n\n"
            "Start with the current Product Handbook for readable operating guidance. The archive chunks preserve full source documentation as explicitly quoted reference blocks, including historical records that are not current runtime instructions. The source-controlled URLs and Trov Product handbook remain separate from this immutable snapshot.\n\n"
            f"Coverage: **{len(entries)} full text documents**, **{sum(e['bytes'] for e in entries):,} source bytes**, **{len(chunks)} Markdown upload chunks**, each at most **650,000 bytes** (below Trov's 750 KB Markdown limit). Source bytes are unchanged; no redactions were necessary in included files. `manifest.json` records individual source hashes, byte counts, source status, document numbers, chunk hashes and exclusions; `MANIFEST.md` is its Markdown upload view. Hashes establish byte identity, not the truth of a scientific claim.\n\n"
            "## Upload order\n\nUpload this navigation index and then the numbered reference-library chunks. Preserve organization visibility and the ReefTrace repository binding. This local build does not publish, send a message, change permissions or commit files.\n\n" + library + "\n\n"
            "## Every feature and its technical reference\n\n| Feature / question | Full source references in this package |\n| --- | --- |\n" + rows + "\n\n"
            "## Current evidence boundaries\n\nOcean trajectories use pinned model currents and hypothetical geometry; the central 2/6 versus flanking 4/6 result is an illustrative what-if, with the original zero-entry tie preserved. Numerical sensitivity is a separate diagnostic and not physical accuracy or ML improvement. Camera preview is not calibrated tank drift or a physical trial. Chalk explains exact evidence but does not replace deterministic physics; provider readiness is not a live response. Photon acceptance is not necessarily delivery. Historical protocols and test counts retain their dates and scope.\n\n"
            "## Deliberate exclusions and binary references\n\n"
            f"- {len(exclusions)} canonical Grok bundle/raw capture files are listed with exact hashes in the manifest, but are covered by the separate [Grok evidence bundle](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/grok-evidence-bundle.md) rather than duplicated. Contribution ledgers, build records and the evidence README are included. Publication is verified in a separate receipt.\n"
            "- Private/local/run directories, `.env`, credentials, contact routing, personal images, recorded camera frames and local databases are never collected.\n"
            "- Raw datasets, JSON evaluation artifacts, executable source, dependencies, generated build output and PDFs/images are not embedded in this text-only reference archive. Their human README/method documentation is included where present.\n"
            "- Binary build references remain linked: [rig guide PDF](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/tideward-rig-guide.pdf), [rig connections](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/assets/tideward-rig-connections.png), [measured map diagram](https://github.com/Jose-Gael-Cruz-Lopez/reeftrace/blob/main/docs/assets/tideward-rig-measured-map.png). These are planned/reference assets, not completed physical measurements.\n"
            "- The archive builder itself and this export directory are excluded from source collection to prevent recursion. Existing source documents are never modified by the builder.\n\n"
            "## Complete source inventory\n\n| Document | Source / archive location | Source bytes | State at capture |\n| --- | --- | ---: | --- |\n" + source_list + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true", help="Build only after documentation owners confirm source readiness.")
    args = parser.parse_args()
    if not args.snapshot:
        raise SystemExit("Inventory builder is ready; pass --snapshot only after docs sources are ready.")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if head != BASELINE:
        raise ValueError("The requested baseline changed; update the explicit snapshot label before building.")
    captured = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    tracked = set(subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines())
    changed = set(subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True).splitlines())
    paths, exclusions = sources()
    entries = []
    for number, path in enumerate(paths, 1):
        payload = path.read_bytes()
        rel = path.relative_to(ROOT).as_posix()
        check_private(payload.decode("utf-8"), rel)
        entries.append({"number": number, "source_path": rel, "bytes": len(payload),
                        "sha256": sha(payload), "source_status": "untracked_working_tree" if rel not in tracked else "modified_working_tree" if rel in changed else "tracked_at_baseline",
                        "payload": payload})
    groups: list[list[dict]] = [[]]
    for entry in entries:
        candidate = groups[-1] + [entry]
        body = header(len(groups), candidate, captured) + "".join(section(e) for e in candidate)
        if len(body.encode()) > MAX_BYTES:
            if not groups[-1]:
                raise ValueError(f"One document exceeds the upload bound: {entry['source_path']}")
            groups.append([entry])
        else:
            groups[-1] = candidate
    outputs = {}
    chunks = []
    for part, group in enumerate(groups, 1):
        filename = f"{part:02d}-reference-library.md"
        payload = (header(part, group, captured) + "".join(section(e) for e in group)).encode()
        if len(payload) > MAX_BYTES:
            raise ValueError("Chunk packing exceeded its bound")
        for entry in group:
            entry["chunk"] = filename
        check_private(payload.decode(), filename)
        outputs[filename] = payload
        chunks.append({"file": filename, "bytes": len(payload), "sha256": sha(payload),
                       "document_count": len(group), "first_document": group[0]["number"], "last_document": group[-1]["number"]})
    index = index_text(entries, chunks, exclusions, captured).encode()
    check_private(index.decode(), "README.md")
    outputs["README.md"] = index
    manifest = {"schema_version": 1, "kind": "PUBLIC_DOCUMENTATION_WORKING_TREE_SNAPSHOT", "repository_url": REPOSITORY,
                "captured_at_utc": captured, "git_source_baseline": BASELINE,
                "working_tree_scope": "Includes numerical-sensitivity documentation not yet pushed at capture; source baseline alone does not identify all archived content.",
                "source_document_count": len(entries), "source_bytes": sum(e["bytes"] for e in entries),
                "source_content_modified": False, "upload_chunk_max_bytes": MAX_BYTES, "publication_performed": False,
                "privacy_scan": {"passed": True, "categories": list(PATTERNS), "credential_files_read": False, "private_media_included": False, "redactions_required": False},
                "index": {"file": "README.md", "bytes": len(index), "sha256": sha(index)}, "chunks": chunks,
                "sources": [{k: v for k, v in e.items() if k != "payload"} for e in entries],
                "external_canonical_grok_coverage_not_duplicated": exclusions,
                "general_exclusions": ["Private/local/runs, credentials, contacts, camera frames and databases", "Raw datasets/JSON evaluations/executable code/dependencies/generated builds", "Binary PDF/image assets are linked only", "Export directory and builder are excluded to prevent recursion"]}
    outputs["manifest.json"] = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
    check_private(outputs["manifest.json"].decode(), "manifest.json")
    outputs["MANIFEST.md"] = ("# Tideward documentation archive manifest\n\n"
                              "Machine-readable source: `manifest.json`. Its SHA-256 is "
                              f"`{sha(outputs['manifest.json'])}`. This is the exact manifest rendered for a native Markdown artifact; it does not publish or commit anything.\n\n"
                              "```json\n" + outputs["manifest.json"].decode() + "```\n").encode()
    check_private(outputs["MANIFEST.md"].decode(), "MANIFEST.md")
    for entry in entries:
        if sha((ROOT / entry["source_path"]).read_bytes()) != entry["sha256"]:
            raise ValueError(f"Source changed during snapshot; rerun after it is stable: {entry['source_path']}")
    OUT.mkdir(parents=True, exist_ok=True)
    for filename, payload in outputs.items():
        (OUT / filename).write_bytes(payload)
    for old in OUT.glob("[0-9][0-9]-reference-library.md"):
        if old.name not in outputs:
            old.unlink()
    print(json.dumps({"source_documents": len(entries), "source_bytes": manifest["source_bytes"], "chunks": chunks,
                      "index_bytes": len(index), "manifest_bytes": len(outputs["manifest.json"]), "manifest_markdown_bytes": len(outputs["MANIFEST.md"]), "canonical_grok_files_not_duplicated": len(exclusions), "privacy_scan_passed": True}, indent=2))


if __name__ == "__main__":
    main()
