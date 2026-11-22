# Conceptual / semantic search for NOMAX

Research notes, not a decision record and not implemented. Goal: a query like
«زودپز» should surface home-appliance repair businesses even though that word
appears nowhere in their name or description.

Date: 2026-11-18

---

## TL;DR

For this app the «زودپز → تعمیر لوازم خانگی» gap is not mainly a vector-database
problem. It is a **vocabulary/domain-knowledge problem**: the query is a
*product*, while every business document is written in *service* vocabulary.
The most reliable fix is a small **query-understanding layer** that maps a query
to a concept and then to the existing category/subcategory tree. Embeddings and
LLM expansion are valuable, but as the second and third layers — not as the
first move. A dedicated search engine is premature for a single-city directory.

---

## 1. What the current system does, and why the example fails

Today search is `ILIKE '%term%'` over name, short/long description, address,
phones, owner name and business tags (`backend/app/services/business_search.py`),
with a relevance tier and then distance/rating/newest ordering. There is no
normalization, no stemming, no synonyms, no embeddings.

So each of these is a miss unless the exact substring exists:

| User types | What blocks it |
|---|---|
| `زودپز` | Business says «تعمیر لوازم خانگی / تعمیر لوازم برقی» — zero shared substring |
| `زودپزها` | Persian plural suffix; `%زودپز%` happens to match, but `یخچال‌ها` vs `یخچال ها` may not |
| `يخچال` (Arabic yeh) | Different Unicode code point from `یخچال` |
| `میکروویو` vs `مایکروویو` | Typo/variant |
| `لوازم خانگی` | Matches the business's category/subcategory, but search **does not look at category names** — only free text and business tags |

Two useful assets already exist in the repo:

- `search_analytics.py` logs every first-page query with its result count and
  inferred category — the raw material for a zero-result / unmet-demand loop.
- `CATEGORY_ALIASES` in `category_suggestions.py` is a hand-built Persian
  term → category map. It is already a **prototype of a concept dictionary**,
  just wired to business creation instead of search.

Key conclusion: build **one shared query-understanding service**, used by search,
analytics and category suggestions, instead of three separate keyword maps.

---

## 2. Three distinct gaps, three different tools

1. **Lexical gap** (spelling, ZWNJ, Arabic/Persian letters, plurals, typos)
   → text normalization + trigram/FTS + light stemming.
2. **Conceptual gap** (`زودپز` is an *instance* of «لوازم خانگی»)
   → concept dictionary / ontology mapping into the existing taxonomy.
3. **Paraphrase gap** (`چیزی که برای پخت سریع غذا لازمه`)
   → embeddings, optionally LLM reformulation.

No single technique covers all three; a layered pipeline does.

---

## 3. Options, with fit for this project

### A. Persian normalization + better lexical matching — *must do, cheapest*

- Unify **ی/ي/ى**, **ک/ك**, ZWNJ (نیم‌فاصله), diacritics, Persian/Arabic
  digits, and whitespace variants. Dedicated engines do exactly this for
  Persian (Charabia normalizes yeh/kaf variants, digits and ZWNJ; Lucene's
  Persian analyzer tokenizes around ZWNJ and standardizes farsi-yeh/keheh).
  Doing it yourself means storing a normalized copy of each searchable field
  (or a normalized expression index), because Postgres has no built-in Persian
  configuration.
- `pg_trgm` GIN index + `similarity()` gives typo tolerance and fast `%…%`
  without a new service.
- Persian has productive suffixes (`ها`, `های`, `ی`, `تر`); Hazm's
  normalizer/stemmer shows the standard approach, but a *small* suffix list or
  trigram similarity is usually enough for shop names.
- **Does not solve زودپز.** It solves variants and typos.

### B. Concept dictionary / lightweight ontology — *highest ROI for the example*

A small table: `term → concept → category/subcategory + expansion terms`, e.g.
`زودپز → لوازم آشپزخانه → repairs/home_appliance → [تعمیر لوازم خانگی, تعمیر لوازم برقی]`.

- Reuse the seed taxonomy: `seed_data/categories.json` already has subcategory
  names and `standard_tags` (`تعمیر یخچال`, `تعمیر لباسشویی`, …). Those are the
  seed vocabulary.
- Reuse `CATEGORY_ALIASES`; add product nouns per subcategory (زودپز، چرخ گوشت،
  جاروبرقی، مایکروویو، پنکه، آبگرمکن…).
- Optionally seed synonyms from **FarsNet** (Persian WordNet, >100k lexical
  entries, ~40k synsets); the literature shows FarsNet-based query expansion
  improves Persian IR. But curation against *this* taxonomy matters more than a
  general WordNet.
- Use **`SearchLog` zero-result queries** as the backlog: every query with
  `results_count = 0` becomes a candidate mapping, reviewed in admin. That is a
  self-improving loop with no ML.
- Retrieval behavior: resolve the query to concepts → **boost/hard-filter** the
  matching category/subcategory → merge with lexical matches. Fallback chain:
  exact filter → sibling subcategories → whole category → lexical/vector, so a
  concept hit never produces an empty page.
- Admin UX: every concept mapping is editable with an audit trail — the same
  pattern as categories/tags today.

Why this is the right first move: the corpus is one city and the taxonomy is only
18 categories / 188 subcategories. The label space is tiny, the domain is stable,
and the expensive part of semantic search (understanding *this* domain) is
exactly what a curated dictionary captures deterministically. It is also
explainable and debuggable.

### C. Reuse Laya as a query classifier — *project-specific, low infra*

Laya is already running for business→category suggestions with a two-stage
category-then-subcategory design and a diagnostics UI. The same machinery can
classify a **query** into a subcategory. Whether Laya understands «زودپز» well
enough is an empirical question — the existing benchmark showed zero-shot 17-way
decisions on noisy shop names were unreliable — but product nouns may be easier
than shop names. If it works, it gives concept mapping for free, with scores that
can be thresholded and traced. Treat it as an experiment measured on a labelled
query set before production.

### D. Embeddings + `pgvector` (hybrid retrieval) — *best for the long tail*

- Enable `pgvector` (already on Postgres; supports HNSW/IVFFlat and
  half-precision vectors) and store one vector per business, built from an
  **enriched document**: name + description + category name + subcategory name +
  tags + service terms. Enrichment matters more than the model: the raw
  description alone rarely contains product words.
- Query time: embed the query and run **hybrid retrieval** — lexical top-N and
  vector top-N merged with Reciprocal Rank Fusion (RRF is the standard,
  score-normalization-free fusion; pgvector ships an RRF example). Keep the
  existing distance/rating sorting as tie-breakers.
- Model choice for Persian, based on the PTEB Persian benchmark:
  `PartAI/Tooka-SBERT-V2-Small` (~123M params, retrieval avg ≈ 61.2) is roughly
  on par with `multilingual-e5-base` (≈ 63.9) at less than half the size;
  `jina-embeddings-v3` is stronger (≈ 65.2) but much heavier. A small model plus
  enriched documents is the right trade-off here.
- Serving: keep the **same architectural pattern as Laya** — a separate
  embedding sidecar (e.g. Hugging Face **TEI**, a small Docker image built for
  exactly this) behind HTTP, so the API image stays free of torch. Batch-embed
  businesses on create/update via the existing worker/outbox; re-embed when the
  model or document template changes (store model name/version with the vector).
- Limits: a generic multilingual model may place «زودپز» near «آشپزخانه» but not
  necessarily near «تعمیر لوازم خانگی». Vector search is strongest for
  paraphrases and long-tail phrasing; it should complement, not replace, the
  concept layer.

### E. LLM query understanding / expansion — *optional third layer*

Production search teams (Yelp, Instacart) use LLMs to classify, rewrite and
expand queries. Two ways to apply it here:

1. **Query time**: `زودپز` → `{concept: لوازم خانگی, expansions: [تعمیر لوازم خانگی,
   تعمیر لوازم برقی]}`. Best long-tail coverage, but adds latency, cost and
   hallucination risk; cache aggressively and keep a deterministic fallback.
2. **Index-time enrichment** (better first step): for each subcategory, generate
   the list of appliances/products it covers and store it as searchable
   synonyms/concepts. No query-time latency, human-reviewable, one-off cost.

Note: Laya is a *classifier*, not a generator — it can choose among existing
concepts but cannot invent expansion terms. A small instruct model would be a
separate sidecar/service.

### F. Dedicated search engine — *not yet*

- **Meilisearch**: since v1.21 (Sept 2025) it has dedicated **Persian**
  segmentation/normalization (yeh/kaf variants, digits, ZWNJ), typo tolerance,
  synonyms, and hybrid search with local or REST embedders. Lowest-ops option if
  search outgrows Postgres.
- **OpenSearch/Elasticsearch**: Lucene's Persian analyzer works, but it is a
  heavy operational addition for a few hundred businesses.
- **Typesense**: handles ZWNJ and offers locales/vector search, but its Persian
  story is less specialized than Meilisearch's.

Verdict: stay with Postgres until relevance work becomes the bottleneck, then
reconsider Meilisearch. Every layer above (normalization, concepts, embeddings)
survives a later engine migration.

---

## 4. Recommended architecture

One **query-understanding pipeline** feeding the existing search:

```
raw query
  → normalize (Persian chars, ZWNJ, digits, spacing)
  → concept resolver (dictionary → Laya → optional LLM, with cache)
       {category, subcategory, expansion terms, confidence}
  → retrieval
       lexical (normalized trigram/FTS, existing fields + category names)
       + concept boost/filter
       + vector top-N (if enabled)
  → fuse (RRF) → existing relevance/distance/rating ordering
  → log query, resolved concept, result count (SearchLog)
```

Staged rollout:

| Stage | What it adds | Effort | Risk |
|---|---|---|---|
| 1 | Normalization + trigram + concept dictionary seeded from `standard_tags`/`CATEGORY_ALIASES` + zero-result review loop | days | low; deterministic |
| 2 | Query → subcategory classification (Laya experiment, dictionary fallback) | ~1 week | medium; needs labelled queries |
| 3 | Embedding sidecar + `pgvector` hybrid with RRF | 1–2 weeks | medium; model/doc-template drift, reindexing |
| 4 | LLM expansion (offline enrichment first, query-time later) | optional | latency/cost/hallucination |
| 5 | Meilisearch only if search becomes a large product surface | later | new service + index sync |

### How «زودپز» behaves under this design

1. Normalization: same string, no change.
2. Concept resolver: dictionary hit `زودپز → لوازم خانگی → repairs/home_appliance`
   (curated once, or proposed by Laya/LLM and approved in admin).
3. Retrieval: boost `home_appliance` businesses and add expansion terms
   «تعمیر لوازم خانگی/برقی» to the lexical query; if fewer than N results,
   relax to the `repairs` category; then fall back to vector similarity.
4. Ranking: concept matches first, then lexical tier, then distance/rating —
   consistent with today's relevance tiers.
5. Learning: if «زودپز» produced zero results today, `SearchLog` now records
   that; the admin dashboard shows it as unmet demand and the mapping gets added.

---

## 5. Evaluation and guardrails

- Build a **golden set** of ~100 real queries from `SearchLog`, labelled with the
  expected subcategory or business. Include variants, typos, ZWNJ, plurals,
  Finglish.
- Track zero-result rate, Recall@10 by category, MRR/nDCG, and the share of
  queries resolved by each layer (dictionary vs Laya vs vector vs raw lexical).
  Layer attribution is what tells you where to invest next.
- A/B the concept layer alone before adding embeddings; if the dictionary already
  resolves most queries, embeddings may only be needed for the long tail.
- Cache query→concept and query→vector in Redis (already deployed); log
  model/version with vectors and reindex on model changes.
- Keep the dictionary human-owned: automatic proposals from logs are fine, but
  approve before they affect production. One bad mapping can hide an entire
  category.

---

## 6. What to avoid

- **Elasticsearch/OpenSearch now** — significant ops for one city's data;
  Postgres + `pgvector` + a sidecar matches the existing Laya pattern.
- **A Persian "stemmer" inside Postgres** — there is no built-in Persian FTS
  config; either pre-normalize/stem in Python on write, or rely on trigrams.
  Do not expect `to_tsvector('persian', …)` to exist.
- **Vector search alone** — least reliable exactly on the product→service jump
  that motivated this research.
- **Query-time LLM as the first step** — highest cost, least debuggable; start
  with the dictionary plus offline enrichment.
- **Auto-applying learned mappings** without review — silent relevance
  regressions are hard to notice.

---

## Sources

- Persian FTS options in Postgres, no built-in config and normalization caveats:
  [dba.stackexchange](https://dba.stackexchange.com/questions/206002/how-to-use-full-text-search-in-persian-using-postgresql/234112),
  [pg_trgm docs](https://www.postgresql.org/docs/current/pgtrgm.html)
- Persian normalization specifics (yeh/kaf/ZWNJ):
  [Meilisearch Charabia Persian support](https://github.com/meilisearch/meilisearch/issues/5847),
  [Lucene PersianAnalyzer](https://lucene.apache.org/core/8_11_3/analyzers-common/org/apache/lucene/analysis/fa/PersianAnalyzer.html)
- Meilisearch Persian support and hybrid search:
  [language docs](https://www.meilisearch.com/docs/resources/help/language),
  [v1.21 release](https://github.com/meilisearch/meilisearch/releases/tag/v1.21.0),
  [synonyms](https://www.meilisearch.com/docs/learn/relevancy/synonyms)
- Typesense locales/ZWNJ: [locale docs](https://typesense.org/docs/guide/locale.html)
- pgvector and hybrid RRF:
  [pgvector](https://github.com/pgvector/pgvector),
  [RRF example](https://github.com/pgvector/pgvector-python/blob/master/examples/hybrid_search/rrf.py),
  [hybrid search with Postgres](https://jkatz05.com/post/postgres/hybrid-search-postgres-pgvector/)
- Persian embeddings / PTEB numbers:
  [Tooka-SBERT-V2-Small](https://huggingface.co/PartAI/Tooka-SBERT-V2-Small),
  [multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small)
- Embedding serving: [Hugging Face TEI](https://huggingface.co/docs/text-embeddings-inference/en/index)
- FarsNet query expansion: [Improving IR Results for Persian Documents using FarsNet](https://arxiv.org/html/1811.00854v1)
- LLM query understanding in production:
  [Yelp](https://engineeringblog.yelp.com/2025/02/search-query-understanding-with-LLMs.html),
  [Instacart via ZenML](https://zenml.io/llmops-database/rebuilding-query-understanding-for-e-commerce-search-with-llms)
- Persian normalization/stemming library: [Hazm](https://github.com/roshan-research/hazm)

---

### Open questions before committing to Stage 2

- Not benchmarked: Laya's accuracy on product nouns like «زودپز».
- Not measured: the actual zero-result rate in `SearchLog` today.

Both are quick first experiments. Main risk: whichever concept layer is built
becomes curated data that needs an owner; without one it silently rots.
