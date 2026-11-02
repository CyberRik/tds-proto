# TDS nature-of-payment classifier (prototype)

Jurisdiction: India, Income-tax Act 2025 (in force from
1 April 2026), with transition to/from the 1961 Act.

The LLM only labels the nature of payment and quotes its
evidence. Code chooses the Act, the section, the rate and
the amount. A CA reviews anything uncertain or contested.

## Files
- `rules.py`: rule rows (each with a source, a verified
  flag and both Acts' references), Act selection by the earlier of
  credit or payment, TDS and exposure arithmetic
- `classify.py`: keyword baseline (non-AI), LLM classifier
  (closed label set, JSON output), verbatim evidence check
- `router.py`: review triggers, shadow mode
- `invoices.json`: 15 synthetic invoices (all made up)
- `vendor_history.json`: synthetic CA-approved history
- `test_core.py`: tests for the deterministic parts
- `run.py`: runs everything, writes `results.md` and
  `audit_log.jsonl`

## Run
```
pip install pytest
python -m pytest -q          # deterministic tests
python run.py --baseline     # no API key needed

python run.py                # full pipeline
python run.py --replay       # re-route saved model outputs
python run.py --resume       # call the model only for
                             # invoices not yet in the log
```
Keys are read from `.env` (git-ignored):
```
OPENROUTER_API_KEY=sk-or-...
GOOGLE_API_KEY=AIza...
LLM_PROVIDER=openrouter      # optional; or gemini
OPENROUTER_MODEL=<model id>  # optional
GEMINI_MODEL=<model id>      # optional
```
Free model IDs on OpenRouter change. Pick one from
openrouter.ai/models (filter: free) and note it here.
Models used (free tier, per-invoice in `audit_log.jsonl`):
- Current prompt: gemini-3.6-flash (INV01-09),
  gemini-3.7-flash (INV10), gemini-3.5-flash-lite
  (INV11-15). Daily limits and overload stopped one model
  finishing.
- Earlier prompt: nvidia/nemotron-3-ultra-550b-a55b:free,
  all 15, kept in `runs/`.

## Results so far
- Deterministic tests: 13/13 pass.
- Keyword baseline: 11/15. It fails on INV04 and INV05
  (medical and software AMCs, both called technical), INV07
  (excavator with operator, called rent) and INV13 ("tax
  advisory", no keyword match). Three of those four are the
  contested cases, and the baseline is confidently wrong on
  them with no way to say "not sure".
- LLM pipeline, current prompt (Gemini): 13/15 labels
  correct, both runs agree on 15/15, no wrong label would
  auto-post. Misses: INV04 and INV05, called technical; both
  go to review and TDS is the same under both labels.
- Earlier prompt (Nemotron): 14/15. Miss: INV14, called
  contract work. It called INV04 and INV05 contract work, so
  the two models split on all three. Model and prompt changed
  together, so neither alone explains the difference.
- Review load: 9/15 go to review on both runs, including
  4/10 non-contested. The 6 that would auto-post are all
  labelled correctly, but nothing posts in shadow mode, and
  which 6 depends on the model.
- The router change was tuned on these same 15 invoices.

## Known limits
- Evidence check is weak: passing shows a quote is real, not
  that it supports the label. Median quoted share was 99% on
  the earlier run and 62% on the current one, with one at 97%.
- The classifier reads the invoice line, but the
  contract decides. In Balabhai Nanavati (Bombay HC, 2025)
  the court required each AMC to be analysed separately,
  so contract text is not yet an input.
- Exposure counts only the TDS difference, not interest,
  penalties or disallowance.
- The sample is one free model on 15 synthetic invoices. I
  wrote both the prompt guidance and the expected labels.
- Expected labels are my reading of public guidance, not
  a practitioner's; no CA has replied yet. Contested cases are marked as such.
- Rule rows are checked against s.393(1) of the Act as
  amended by the Finance Act 2026.
- The payer is assumed to be a designated/specified person
  (s.402(11), s.402(37)). Individual and small HUF payers
  fall under different rows.
- s.393(1)(a) "entire amount" is applied as a catch-up of
  earlier untaxed sums on the invoice that crosses the
  aggregate limit. `ytd_before` is a single total, not
  tracked per nature of payment or contract.
- Rule rows have no effective dates of their own. The only
  date logic picks the Act, so rates assume FY 2025-26 on.
- Out of scope: non-residents (s.393(2)), salary
  (s.392), TCS, lower-deduction certificates, PAN-missing
  higher rates, GST-inclusive amounts.
