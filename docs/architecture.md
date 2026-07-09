# Architecture: Why Hybrid Extraction

## The core problem

Document extraction tools tend to pick one of two extremes:

1. **Pure regex/template parsing** — fast and free, but brittle. The moment
   a vendor changes their invoice layout by a few pixels, the rules break.
2. **Pure LLM extraction** — flexible and robust to layout changes, but
   every single document costs an API call, adds latency, and depends on
   an external provider being up and affordable.

Most real-world use cases (a freelancer processing the same three clients'
invoices every month; a small business ingesting receipts from a handful
of recurring vendors) don't need #2 for every document. They need #1 for
the 80% of documents with a layout they've seen before, and #2 as a safety
net for the 20% that don't match anything.

## The routing decision

`src/extractors/router.py` implements three modes, selectable per-run or
per-request:

| Mode | Behavior | When to use |
|---|---|---|
| `template` | Only tries configured templates. Fails fast if nothing matches. | You know all incoming documents match a known layout and want zero AI cost. |
| `ai` | Always calls the configured LLM provider. | Documents are one-off, highly varied, or you don't have a template yet. |
| `auto` (default) | Tries template matching first; falls back to AI only if no template matches **or** confidence is below `routing.auto_fallback_confidence` in `config.yaml` (default `0.75`). | The common case — mixed batches of known and unknown layouts. |

### How template matching produces a confidence score

Each template in `config.yaml` defines regex/positional rules per field.
`TemplateExtractor.find_matching_template()` scores every configured
template by how many **required** fields it successfully extracts from the
document text, and picks the highest-scoring one. `_confidence()` then
computes:

```
confidence = (required_fields_found / required_fields_total) - error_penalty
```

If that confidence clears `auto_fallback_confidence`, the router trusts
the template result and never spends an LLM call. If it doesn't — say,
the document's layout doesn't resemble any configured template — the
router hands the same raw text to `AIExtractor`, which prompts the
configured LLM provider (OpenAI / Anthropic / Gemini, chosen via
`AI_PROVIDER`) with a JSON-schema built directly from `config.yaml`'s
`fields:` list. This keeps both extraction paths in sync automatically:
add a field to the config once, and both the template rules (if you add a
matching regex) and the AI prompt schema pick it up.

### Worked example

Given the four synthetic documents in `sample_data/`:

- `invoice_acme_supplies.pdf` and `invoice_brightpath_logistics.pdf` both
  match `standard_invoice_v1` — every required field is found via regex,
  confidence lands at `1.0`, no AI call happens.
- `receipt_daily_grind_cafe.pdf` matches `standard_receipt_v1` the same way.
- `irregular_summit_consulting.pdf` is deliberately written in prose
  (`"Amount owed before applicable tax comes to 2100.00"` instead of
  `"Subtotal: 2100.00"`) — no template rule matches, confidence is `0.0`,
  and in `auto`/`ai` mode the router falls back to the LLM, which reads
  the prose and correctly extracts the same fields a human would.

## OCR as a pre-processing step, not a third path

OCR isn't a separate extraction engine — it's a text-acquisition step that
runs *before* routing, when `document_reader.py` detects a PDF page has no
usable text layer (i.e., it's a scanned image, not digitally generated
text). Once OCR produces text, that text flows into the same
template-vs-AI routing decision as any other document. OCR confidence
(from `pytesseract`'s per-word confidence scores) is checked against
`config.yaml`'s `ocr.min_confidence` and logged when it's too low, so a
noisy scan surfaces as a flagged/partial result instead of silently
producing wrong data.

## Error isolation

`batch_processor.py` wraps every single document's processing in a
try/except boundary. A malformed PDF, an OCR failure, or an unexpected
exception in either extractor is caught, converted into an
`ExtractionResult` with `status=FAILED` and a human-readable message in
`.errors`, and the batch moves on to the next file. Nothing about one bad
document can crash a run of 200 others.
