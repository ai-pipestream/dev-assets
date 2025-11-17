## Parser Orchestrator Architecture (RFC)

### Status
- Draft
- Owner: Parser Team
- Last updated: 2025-08-16

### Summary
Define a modular parser orchestrator that can route documents to multiple parser backends (Tika, gRPC microservices, lightweight in-memory parsers), support 1:1 and 1:M outputs (e.g., archives), and apply fallback/merge strategies with strong typing, data fidelity, and security in mind. This RFC also captures configuration knobs, streaming/backpressure, discovery/integration, error taxonomy, observability, and a pragmatic migration plan.

### Goals
- **Strongly-typed outputs**: Emit `TikaResponse` with document-type messages and overlay metadata (e.g., Dublin Core, Creative Commons) using our protobufs.
- **No data loss**: Preserve unmapped fields and raw values (via `_raw` or `additional_*` fields).
- **Composability**: Support multiple parser implementations, configured per MIME/extension, with overrides and fallback.
- **Scalability**: Stream inputs/outputs, apply backpressure, and parallelize safely.
- **Security-first**: Minimize attack surface (e.g., archive parsing), and apply policy controls.

### Non-Goals
- Implement all parser backends at once.
- Build a full policy engine in v1.
- Replace Tika entirely.

---

## Architecture Overview

### Core Components
- **Parser Orchestrator** (this module):
  - Accepts a `PipeDoc`, determines document type (MIME + extension + heuristic), constructs a parse plan, and executes it.
  - Aggregates results into a single `TikaResponse` and places it into `PipeDoc.structured_data` (`google.protobuf.Any`).
- **Parser Backends**:
  - **Tika** (embedded): current default; robust format coverage; configurable via `TikaConfig` and runtime knobs.
  - **gRPC Parsers** (remote): vertical microservices for specialized formats or expensive models (e.g., OCR, PDFs, media, WARC alt).
  - **Lightweight/In-memory Parsers**: format-specific helpers (e.g., EPUB OPF/NAV, ZIP listings, simple text heuristics).

### Data Contracts
- Primary schema: `grpc/grpc-stubs/src/main/proto/tika/*.proto`.
- **Strong typing** + `_raw` fallbacks for ambiguous types.
- Overlay metadata: `DublinCore` and `CreativeCommons` are additive to the primary oneof type.

### Detection
- `DocumentTypeDetector` inspects `Content-Type`, filename, and key metadata to determine primary type.
- Secondary overlays are inferred by presence of fields (e.g., XMPRights) regardless of primary type.

---

## Parse Plans

### 1:1 vs 1:M
- **1:1**: PDF, Office, Image, HTML, RTF, Font, EPUB, Database, Creative Commons overlay, ClimateForecast.
- **1:M**: Archives (ZIP, TAR), containers (WARC), media with embedded streams. These should produce:
  - Parent `PipeDoc` (index summary) + child `embedded_docs` or separate documents via a fan-out pipeline stage.

### Plan Steps (example)
- Detect primary type.
- Build a plan with steps (ordered):
  - Content extraction (optional per type)
  - Metadata extraction (primary)
  - Overlay extraction (DublinCore/CC/etc.)
  - Lightweight enrichers (e.g., EPUB OPF/NAV; PDF XMP pass)
  - Post-processing (chunk plan, heuristics)

### Fallback/Merge Strategy
- **Strict → Lenient** fallback chain per type (per-config), e.g.,
  - PDF: Native → XMP → heuristic
  - WARC: jwarc strict → normalizer → alternative reader (optional) → graceful degrade
- **Merge rules**:
  - Prefer strongly-typed fields if parse succeeds.
  - Preserve original strings in `_raw` if parse fails.
  - Keep unmapped in `additional_metadata`.

---

## Parser Types

### Tika (Embedded)
- `modules/parser/...` orchestrates Tika parse.
- Configurable detectors/parsers; special handling for problematic types (e.g., fonts bypass).

### gRPC Parsers (Remote)
- Used for CPU/GPU-heavy tasks, specialized formats, and safety isolation.
- Discoverable via Consul/service registry.
- Contract: request `PipeDoc`, response `TikaResponse` (or a submessage packed in `Any`).

### Lightweight/In-memory Helpers
- EPUB OPF/NAV parsing (`EpubStructureExtractor`).
- ZIP listings (safe mode): metadata-only without content extraction.

---

## Streaming & Backpressure
- Use reactive streams (`Mutiny`) for ingest and fan-out.
- **Max content length** knobs per type to avoid overload.
- Avoid large `structured_data` payloads (strip large base64 hints after usage).

---

## Configuration Knobs
- Global:
  - Parse timeout, max content length, max outbound gRPC message size, parallelism.
- Per type (examples):
  - PDF: enable/disable XMP pass, font analysis.
  - HTML: JSoup options (sanitization, meta extraction).
  - Archives: detector/parser enable flags, safe listings only.
  - WARC: strictness level, normalizer enable.
- Source of truth: `ProcessConfiguration` + dynamic registry overrides.

---

## Discovery & Routing
- Service discovery (e.g., Consul) for remote parsers.
- Router picks backend by MIME, extension, or policy tag (e.g., "sensitive").
- Local preference with remote fallback, or vice versa.

---

## Error Taxonomy
- **Status**: SUCCESS, PARTIAL, FAILED, TIMEOUT.
- **Warnings**: parsing warnings (e.g., detector retries, disabled parsers, fallback used).
- **Errors**: typed categories per backend (e.g., `ArchiveException`, `ParsingException`).
- Persist in `TikaParseStatus` and `base_fields.parse_warnings`.

---

## Security & Policy
- Disable risky parsers/detectors by default (archives, scripts) unless explicitly enabled.
- Size/time caps per step.
- Quarantine/skip embedded executables.
- Allowlist/denylist by MIME/extension.
- Sandbox remote heavy parsers via gRPC.

---

## Observability & Metrics
- Per-step timings; parse plan tracing.
- Counters: successes, partials, failures, fallbacks used.
- Payload sizes (content and structured data) for capacity planning.
- Sampling logs for large inputs.

---

## Chunking
- Emit a **chunk plan** (optional structure) using TOC/spine (EPUB), headings (HTML), page breaks (PDF), scene/time markers (media), etc.
- Downstream chunker reads the plan to segment body text.

---

## Versioning & Compatibility
- Protobufs are additive; use `optional` and `_raw` to avoid breaking changes.
- Record parser/plan versions in `base_fields` for reproducibility.

---

## Migration Plan (Phases)
- **Phase 1 (current)**: Strongly-typed builders for PDF, Office, Image, Email, Media, HTML, RTF, WARC, Font, EPUB (with OPF/NAV), overlays (DublinCore, CreativeCommons). Tests & samples.
- **Phase 2**: ClimateForecast, Database; archive-safe listings; initial chunk plan outputs.
- **Phase 3**: Introduce remote gRPC parsers for heavy tasks; service discovery; policy controls.
- **Phase 4**: Advanced fallback chains; better normalizers (WARC); security hardening; rich observability.

---

## Test Strategy
- Integration tests per type: sample sets under `modules/parser/src/test/resources/sample_doc_types/...`.
- Skip tests gracefully if samples missing; assert typed fields present.
- Property-level coverage tests (e.g., PDF field coverage).

---

## Notable Decisions
- **Raw fallbacks**: `_raw` fields added for important ambiguous types.
- **Overlays**: Dublin Core and Creative Commons always attempted, independent of primary type.
- **Font bypass**: Avoided Tika archive detectors for fonts; minimal content parse with metadata enrichment.
- **EPUB structure**: Direct OPF/NAV parse to enrich spine/manifest/TOC.
- **Payload control**: Remove transient base64 hints before building additional metadata to avoid large gRPC messages.

---

## Open Questions
- Which remote parsers to prioritize (OCR, PDF table extraction, audio transcription)?
- Policy DSL for routing/fallbacks—JSON/YAML vs. code?
- Archive support scope vs. security posture.

---

## References
- Code: `modules/parser/src/main/java/io/pipeline/module/parser/tika/` builders and utilities
- Schemas: `grpc/grpc-stubs/src/main/proto/tika/*.proto`
- Tests: `modules/parser/src/test/java/io/pipeline/module/parser/**`
