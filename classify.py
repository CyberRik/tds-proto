"""The only probabilistic part: nature-of-payment labelling.

Two classifiers:
  keyword_baseline  - regex rules, the non-AI comparison
  llm_classify      - LLM via OpenRouter or Gemini, closed
                      label set, must quote evidence from
                      the input
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from rules import LABELS

ALLOWED = LABELS + ["unclear"]


def load_env(path=Path(__file__).with_name(".env")):
    """Read KEY=value lines; .env beats the shell's vars."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        name, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            os.environ[name.strip()] = value.strip()


load_env()

# ---------- non-AI baseline ----------

KEYWORDS = [
    (r"\b(rent|lease)\b.*\b(office|premises|building)",
     "rent_land_building"),
    (r"\b(office|premises|building|space)\b.*\brent",
     "rent_land_building"),
    (r"\b(hire|hiring|rental)\b.*"
     r"\b(crane|machine|equipment|excavator)",
     "rent_plant_machinery"),
    (r"\b(commission|brokerage)\b", "commission"),
    (r"\b(audit|legal|advocate|consult)",
     "professional_fees"),
    (r"\b(technical|software|engineer)",
     "technical_services"),
    (r"\b(amc|maintenance|repair|housekeeping|catering"
     r"|advertis|contract)", "contract_work"),
]


def keyword_baseline(text: str) -> str:
    t = text.lower()
    for pattern, label in KEYWORDS:
        if re.search(pattern, t):
            return label
    return "unclear"


# ---------- LLM classifier ----------

GUIDANCE = """\
Guidance (curated; cite when relevant):
G1. CBDT Circular 715 (1995) Q29: routine, normal
    maintenance contracts including supply of spares are
    contract work; where technical services are rendered,
    they are technical services.
G2. Presence of qualified staff alone does not make a
    contract technical services; the dominant nature of
    the work decides.
G3. Tribunals have treated AMCs for AC, lifts and
    computers as contract work; disputes are common for
    medical equipment and software maintenance.
G4. Advertising is within the meaning of "work" for
    contract-payment TDS.
G5. Hiring machinery WITH operator/fuel can be contract
    work; hiring machinery alone for a period is rent.
"""

SYSTEM = f"""\
You classify the NATURE OF PAYMENT on an Indian vendor
invoice for TDS purposes. You do NOT give section numbers,
rates or amounts.

Allowed labels: {", ".join(ALLOWED)}.
Use "unclear" if the text does not let you decide.

{GUIDANCE}
Reply with JSON only:
{{"label": "<one allowed label>",
  "evidence": ["<shortest exact phrases from the invoice
               text that decide the label; never copy the
               whole text>"],
  "alternatives": ["<other plausible labels>"],
  "confidence": "high" | "medium" | "low",
  "guidance_used": ["G1", ...],
  "reason": "<one sentence>"}}
"""

PROVIDERS = {
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key_var": "OPENROUTER_API_KEY",
        "model_var": "OPENROUTER_MODEL",
        "default_model":
            "nvidia/nemotron-3-ultra-550b-a55b:free",
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com"
               "/v1beta/openai/chat/completions",
        "key_var": "GOOGLE_API_KEY",
        "model_var": "GEMINI_MODEL",
        "default_model": "gemini-3.6-flash",
    },
}


def llm_classify(text: str, temperature=0.3) -> dict:
    provider = PROVIDERS[os.environ.get("LLM_PROVIDER",
                                        "openrouter")]
    key = os.environ[provider["key_var"]]
    model = os.environ.get(provider["model_var"],
                           provider["default_model"])
    body = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user",
             "content": f"Invoice text:\n{text}"},
        ],
    }
    raw = post_with_retry(provider["url"], body, key)
    content = raw["choices"][0]["message"]["content"]
    out = parse_json(content)
    out["model"] = model
    return out


def post_with_retry(url, body, key, tries=5, wait=15):
    """Free tiers often return 429 or 503, so back off."""
    for attempt in range(tries):
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if (e.code not in (429, 500, 502, 503)
                    or attempt == tries - 1):
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == tries - 1:
                raise
        time.sleep(wait * 2 ** attempt)


def parse_json(content: str) -> dict:
    """Tolerate code fences; fail closed to 'unclear'."""
    m = re.search(r"\{.*\}", content, re.S)
    try:
        out = json.loads(m.group(0))
    except (AttributeError, json.JSONDecodeError):
        return {"label": "unclear", "evidence": [],
                "alternatives": [], "confidence": "low",
                "reason": "unparseable model output"}
    if out.get("label") not in ALLOWED:
        out["label"] = "unclear"
    return out


# ---------- deterministic evidence check ----------

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def evidence_ok(text: str, evidence: list) -> bool:
    """Every quote must appear verbatim in the input."""
    if not evidence:
        return False
    t = norm(text)
    return all(norm(q) in t for q in evidence)


def evidence_coverage(text: str, evidence: list) -> float:
    """Share of the input quoted. Near 1.0 means the model
    copied everything, so evidence_ok proves little."""
    quoted = sum(len(norm(q)) for q in evidence)
    return round(min(1.0, quoted / len(norm(text))), 2)
