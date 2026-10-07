# Canadian Trucking Compliance Platform — Phase 1 Design Spec

**Date:** 2026-10-07  
**Status:** Design Approved  
**Scope:** Transform Driver Ops from single-company RAG to open-source national platform for all Canadian truckers with Punjabi support

---

## 1. Vision & Goals

### Vision
Create a free, open-source compliance assistant that any trucker in Canada can use to get accurate answers about trucking regulations and best practices across all provinces.

### Business Model
**Open-source community platform** (not SaaS at launch). Everyone uses the same public database of Canadian regulations. No login, no company segmentation, no payments—just truckers asking questions.

### Success Criteria (Phase 1)
- All 13 Canadian jurisdictions covered (federal + 10 provinces + 3 territories)
- 300+ regulation documents ingested
- Punjabi UI fully translated
- ≥90% accuracy on English questions (eval suite)
- <15s response time (90th percentile)
- ≥99% uptime
- Public launch on GitHub + live web interface

---

## 2. Architecture Overview

### Current State
- Single-company RAG system (Maple Freight Inc.)
- Regulations: Ontario, US federal, Canada federal only
- Policies: Company-specific (fictional Maple Freight handbook)
- Languages: English only
- Deployment: Local/single server

### Target State (Phase 1)
- **Open-source national platform**
- Regulations: All Canadian provinces + federal (300+ documents)
- Policies: Removed from Phase 1 (architecture preserved for later SaaS layer)
- Languages: English UI + Punjabi UI; queries in Punjabi supported; answers in English
- Deployment: Cloud-ready, Docker Compose, public web + API

### Component Changes
| Component | Current | Phase 1 | Notes |
|-----------|---------|---------|-------|
| **Corpus** | 18 docs (ON + US + CA) | 300+ docs (all provinces) | Expand, no removal |
| **Policies** | C01-C06 (Maple Freight) | Removed | Architecture preserved for Phase 2 |
| **UI** | English only | English + Punjabi | Language toggle in UI |
| **Queries** | English only | English + Punjabi | bge-m3 supports both |
| **Answers** | English | English (always) | Preserves legal accuracy |
| **Branding** | "Driver Ops" | "Canadian Trucking Compliance" | Reflects scope |
| **Access** | Telegram bot + local chat | Public web app | No authentication |

### Data Flow (Unchanged)
```
Trucker asks question (English or Punjabi)
    ↓
Guardrail node: Is this in-scope? (trucking compliance only)
    ↓
Retrieve node: Hybrid search (BM25 + vector) across all provinces
    ↓
Grade documents node: Relevance scoring
    ↓
Generate answer node: LLM creates response in English
    ↓
Return: Answer + citations (regulation ID, province, source URL)
    ↓
If poor retrieval: Rewrite query and retry (max 2 attempts)
```

---

## 3. Corpus Expansion (All Provinces)

### Target Coverage
```
corpus/regulations/
├── federal/
│   ├── fmvss/              # Federal Motor Vehicle Safety Standards
│   ├── csa/                # Canadian Standards Association
│   └── cvsa/               # Commercial Vehicle Safety Alliance
├── provinces/
│   ├── bc/                 # British Columbia
│   ├── ab/                 # Alberta
│   ├── sk/                 # Saskatchewan
│   ├── mb/                 # Manitoba
│   ├── on/                 # Ontario (existing, keep)
│   ├── qc/                 # Quebec
│   ├── nb/                 # New Brunswick
│   ├── ns/                 # Nova Scotia
│   ├── pe/                 # Prince Edward Island
│   ├── nl/                 # Newfoundland & Labrador
│   ├── yt/                 # Yukon
│   ├── nt/                 # Northwest Territories
│   └── nu/                 # Nunavut
└── manifest.csv            # Metadata: doc_id, title, url, province, language, last_updated
```

### Document Sourcing Strategy
1. **Federal:** Official Canada.ca (Transportation Safety Board, Infrastructure Canada)
2. **Provinces:** Each province's ministry of transportation/motor vehicle website
3. **Versioning:** Track `last_updated` date in manifest.csv
4. **Update cadence:** Quarterly ingestion DAG run; manual trigger available

### Estimated Scope
- Federal regulations: ~30 documents
- Per province: 15-25 documents average
- **Total Phase 1: 300+ documents** (manageable for one ingestion run)

### Metadata Schema
```csv
doc_id,title,source_url,province,doc_type,language,last_updated,file_format
R01,Highway Traffic Act (Ontario),https://ontario.ca/...,ON,regulation,en,2026-10-01,PDF
R02,Alberta Commercial Transport Act,https://alberta.ca/...,AB,regulation,en,2026-09-15,HTML
...
```

### Chunking & Indexing
- **Parsers:** Keep existing Docling (PDF), HTML, Markdown parsers
- **Chunking:** Existing strategy (semantic chunking, ~500 tokens per chunk)
- **Index:** OpenSearch (63 shards, BM25 + vector search)
- **Embeddings:** bge-m3 (multilingual, Punjabi-capable)

---

## 4. Multilingual Support (Punjabi Phase 1)

### Implementation Strategy

#### UI Translation
- Translate `ui/index.html` labels to Punjabi:
  - Chat input placeholder: "ਆਪਣਾ ਸਵਾਲ ਪੁੱਛੋ..." (Ask your question...)
  - Send button: "ਭੇਜੋ" (Send)
  - System panel status: "ਸਿਸਟਮ ਸਥਿਤੀ" (System Status)
  - Error messages: Punjabi translations
- Add language toggle: "English | ਪੰਜਾਬੀ" (top-right corner)
- Store user preference in `localStorage['language']`

#### Query Processing
- Accept Punjabi text in chat input (no preprocessing needed)
- Pass Punjabi query to embedding model (bge-m3 supports Punjabi natively)
- Retrieval: Punjabi query → matches English documents (multilingual embeddings bridge the gap)
- Generation: System prompt in English → LLM responds in English

#### System Prompt Update
```
You are a Canadian trucking compliance assistant.
Users may ask questions in English or Punjabi.
Always respond in English with accurate regulation citations.
If a user asks in Punjabi, respond in English.
Cite the regulation ID, province, and source URL.
```

#### What We Don't Do (Phase 1)
- No Punjabi document translations (Phase 2, if demand warrants)
- No Punjabi prompts or system messages (keep simple, English-driven)
- No language detection (user selects via toggle)

#### Phase 2 Plan
- Professional Punjabi translation of top 20 regulations (most-asked topics)
- French UI + French queries (official bilingual support)
- Spanish UI (growing demographic)

---

## 5. Deployment & Operations

### Infrastructure
**Hosting:** Cloud-agnostic (AWS, DigitalOcean, or on-premises). Decision deferred until after product validation.

**Services (Docker Compose):**
- FastAPI (`api:8000`) — question handling, streaming responses
- PostgreSQL (`postgres:5442`) — document metadata
- OpenSearch (`opensearch:9200`) — chunk search index
- Redis (`redis:6379`) — response cache
- Airflow (`airflow:8081`) — ingestion DAG
- Ollama (host-local, port 11434) — LLM + embeddings

**Database:**
- Postgres: Document metadata (doc_id, title, province, source_url, last_updated)
- OpenSearch: Chunk index (chunk_id, doc_id, text, embedding, province, language)
- Redis: Cache (query → answer, TTL 24h)

### Deployment Checklist
1. Clone repo: `git clone https://github.com/<org>/canadian-trucking-compliance.git`
2. Setup: `make env` (generate .env with secrets)
3. Start: `docker compose up -d`
4. Seed: `make ingest` (fetches & indexes all regulations)
5. Health: `curl http://localhost:8000/api/v1/health`
6. Chat UI: `uv run python ui_server.py` (or expose via reverse proxy)

### Public Access
- **Web:** `trucking-compliance.ca` (or similar domain)
- **API:** Public endpoint for questions (no auth, rate-limited)
- **GitHub:** Open-source repo with README, setup guide, corpus links

### Estimated Costs
| Component | Cost/Month | Notes |
|-----------|-----------|-------|
| Compute (1 server) | $100-150 | 4+ CPU, 8GB RAM |
| Storage (Postgres + OpenSearch) | $10-20 | ~100GB total |
| Bandwidth | $10-20 | Egress only |
| Domain + CDN | $10-15 | Optional; for faster serving |
| **Total** | **~$130-205/month** | Sustainable for Phase 1 |

### Operations & Maintenance
- **Health monitoring:** Daily health check email alerts
- **Corpus updates:** Quarterly ingestion DAG runs (4x/year)
- **Logs:** OpenTelemetry traces to OpenSearch; Langfuse optional for debugging
- **Backups:** Daily snapshots of Postgres + OpenSearch volumes
- **Scaling:** If usage exceeds 1000 req/day, add caching layer + CDN

---

## 6. Success Metrics & Launch Criteria

### Phase 1 Launch Readiness (Pre-Public)
| Metric | Target | Success = |
|--------|--------|-----------|
| Provinces | 13/13 (all) | ✓ Federal + ON + BC + AB + QC + MB + SK + NB + NS + PE + NL + YT + NT + NU |
| Regulations ingested | ≥300 docs | ✓ Diverse coverage across jurisdictions |
| Eval pass rate (English) | ≥90% | ✓ Run `uv run python evals/run_eval.py --mode agentic` |
| Punjabi UI | 100% translated | ✓ All labels, placeholders, errors in Punjabi |
| Response time (p90) | <15s | ✓ Acceptable UX for public |
| Uptime (7-day test) | ≥99% | ✓ No production crashes |
| Documentation | Complete | ✓ README, setup guide, corpus manifest |
| Open-source repo | Public | ✓ GitHub, MIT license, contribution guidelines |

### Phase 1 Success Metrics (Post-Launch)
- **Adoption:** 1000+ unique users in first month
- **Engagement:** 2-3 questions per user average
- **Quality:** <2% error rate (API failures + bad answers combined)
- **Community:** 100+ GitHub stars, positive feedback from trucking forums
- **Technical:** ≥99.5% uptime, <10s response time (p95)

### Phase 2 Decision Criteria (2-3 months post-launch)
- **If usage >1000 req/day:** Invest in SaaS layer (company policies, custom models)
- **If Punjabi demand:** Hire translators for key regulations
- **If government interest:** Explore official adoption / funding

---

## 7. Timeline & Deliverables

### Phase 1 (Weeks 1-4)
| Week | Deliverable |
|------|-------------|
| 1-2 | Expand corpus: fetch & parse all provincial regulations |
| 2-3 | Translate UI to Punjabi; test multilingual retrieval |
| 3-4 | Deploy to cloud; run full eval suite; QA |
| 4 | Launch: public GitHub repo + web interface |

### Phase 2 (Months 2-3, conditional)
- Translate top 20 regulations to Punjabi (if demand exists)
- Add French UI + French queries
- Setup monitoring + analytics
- Community engagement (forums, associations, outreach)

---

## 8. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Regulations change frequently | High | Outdated answers | Quarterly updates; user warning if doc >6mo old |
| Provincial docs hard to find | Medium | Incomplete corpus | Start with 5 largest provinces; expand gradually |
| Punjabi queries don't retrieve English docs well | Low | Poor UX for Punjabi users | bge-m3 is multilingual; test with 50+ Punjabi queries before launch |
| Legal liability (wrong compliance info) | Medium | Lawsuits, reputation | Add disclaimer: "Not legal advice; verify with official sources" |
| Costs exceed budget | Low | Unsustainable | Monitor OpenSearch usage; add caching layer if needed |

---

## 9. Assumptions & Constraints

### Assumptions
- Ollama continues to run on host (no Docker container for LLM)
- bge-m3 embeddings support Punjabi well enough (test needed)
- Provincial regulations are available online (public sources)
- No legal barrier to indexing public regulations

### Constraints
- **No authentication:** Public access means no company data initially (Phase 2)
- **English answers only:** Avoids translation liability
- **Single-server deployment:** No high-availability setup in Phase 1
- **No real-time updates:** Quarterly ingestion, not live regulatory feeds

---

## 10. Success Definition

**Phase 1 is successful when:**
1. ✓ Platform covers all 13 Canadian jurisdictions
2. ✓ Punjabi-speaking truckers can ask questions in Punjabi
3. ✓ Public launch on GitHub with 100+ stars in first month
4. ✓ Evaluation suite passes ≥90% on English questions
5. ✓ <15s response time, ≥99% uptime
6. ✓ Positive community feedback (Reddit, Punjabi forums, trucking associations)
7. ✓ Sustainability plan for Phase 2 (SaaS layer, if demand exists)

---

## 11. Next Steps

**After spec approval:**
1. Invoke `superpowers:writing-plans` to create detailed implementation plan
2. Assign: corpus expansion, Punjabi translation, deployment setup
3. Execute phase 1 launch in 4 weeks
4. Monitor metrics and iterate based on user feedback

---

**Document Status:** Ready for user review  
**Approval Date:** (awaiting user review)
