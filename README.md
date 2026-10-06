# Driver Ops — corpus & eval kit

Test kit for building the **Driver Ops** RAG agent (trucking compliance + company procedures, answered over Telegram) with the `prod-rag-agent` skill.

## What's here

```
driver-ops/
  fetch_corpus.sh            # downloads the 18 official regulation docs
  corpus/
    regulations/manifest.csv # R01–R18: titles, jurisdiction, official URLs
    company/                 # C01–C06: fictional "Maple Freight Inc." policies
  evals/questions.md         # 24 test questions, expected sources, pass thresholds
```

## Step 1 — download the regulations (on your machine)

```bash
cd driver-ops
bash fetch_corpus.sh
```

Check `corpus/regulations/fetch_log.txt`. Re-run to retry any failures. Every URL is an official government source (Justice Canada, Transport Canada, CBSA, FMCSA, CBP, ontario.ca).

Note: the corpus is deliberately mixed — HTML pages *and* PDFs, Canadian *and* US rules, one older document (R08, 2012). The skill's ingestion assumes PDFs only, so how it handles the HTML files is part of the test.

## Step 2 — build

Open a **fresh** Claude Code session in this folder and paste:

> Build a RAG agent called Driver Ops for a trucking company. Corpus is in `./corpus`: official Canadian/US/Ontario trucking regulations (HTML and PDF, listed in `corpus/regulations/manifest.csv`) and company policy documents in `corpus/company`. Drivers ask questions through Telegram and get short answers that cite the source documents. Domain: trucking compliance and company procedures only; refuse anything else. When company policy and regulation both apply, give both and say which is which. Use `./evals/questions.md` as the acceptance test, with its release thresholds. Follow the build order and pass each stage's check before moving to the next.

Don't name the skill. Whether it picks it up on its own is part of the test.

## Step 3 — what to record

| Check | Pass? | Notes |
|---|---|---|
| Skill loaded without being named | | |
| Read `prod-checklist.md` section B before coding | | |
| Adapted doc key, prompts, abstract handling, source client | | |
| Ingested HTML as well as PDF | | |
| Retrieval hit ≥ 80% (Q01–Q15, Q22–Q24) | | |
| Citations 100% correct | | |
| Q16–Q18 not invented | | |
| Q19–Q21 refused | | |
| Q24 (Punjabi) behaviour | | |

Whatever fails here becomes the next fixes to the skill.

## Disclaimer

Maple Freight Inc., its phone numbers and email addresses are fictional. The regulation documents are the real public sources; check them for currency before using this with a real client.
