# grpc-services — orientation

**These services are NOT part of the pipestream core platform.** They do not
implement the pipestream module contract, are not wired into process-compose
or the platform build, and nothing in core-services/ or modules/ may depend
on them being up. Do not "fix" them to match platform conventions.

## What they are

Standalone gRPC servers for document extraction and search — the GitHub-side
research arm that grew out of the OpenNLP 3.x work. Each wraps a native or
JVM library behind a small, stable gRPC surface so any language can call it.
They are developed on github.com/ai-pipestream (some are mirrored to
Forgejo), unlike the core platform whose source of truth is git.rokkon.com.

| Repo | What it wraps | Notes |
|---|---|---|
| `grpc-libreoffice` | LibreOffice | emits pages from office documents |
| `grpc-calamine` | calamine (Rust) | in-memory Excel/ODS parsing, streams row events |
| `calamine` | — | our fork of tafia/calamine; work happens on `pipestream-main`, `master` mirrors upstream |
| `grpc-lol-html` | lol-html (Rust, Cloudflare) | streams CSS-selector matches out of HTML |
| `grPOIc` | Apache POI | POI-based extraction server |
| `distributed-search` | — | gRPC distributed semantic search engine (collaborative HNSW) |

## Ground rules

- Hosted on GitHub: clone/push against `github.com/ai-pipestream/<repo>`;
  the bootstrap manifest carries explicit `url` overrides for these.
- Related but living elsewhere: `grpc-opennlp-analysis`, `grpc-slow`,
  `mcp-grpc-transport-proto` (Forgejo org); the reference clones of the
  wrapped upstreams (calamine, lol-html, poi…) are under
  `reference-code/`, read-only.
- This file is generated from `dev-assets/config/category-docs/grpc-services.md`
  by the bootstrap — edit it there, not here.
