# V-Vet symptom extraction

A small FastAPI service that turns a farmer's free-text message into structured
clinical findings from a fixed list of nine signs, then decides in plain code
whether the case should be escalated.

## Run it

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env          # then put a key in LLM_API_KEY
set -a; source .env; set +a   # the app reads os.environ; it does not load .env itself
uv run uvicorn app.main:app --reload
```

The LLM client is OpenAI-compatible, so any of these work by changing
`LLM_BASE_URL` / `LLM_MODEL`:

| Provider | `LLM_BASE_URL` | Example model |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| Groq (free tier) | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| OpenRouter | `https://openrouter.ai/api/v1` | `google/gemini-2.5-flash` |
| Ollama (local) | `http://localhost:11434/v1` | `llama3.1` |

`LLM_API_KEY` is required for everything except some local servers, where any
non-empty value (for example `ollama`) works. `LLM_TIMEOUT` defaults to 30s.

```bash
curl -s http://localhost:8000/extract \
  -H 'content-type: application/json' \
  -d '{"message": "There'\''s foam coming from her nose and she can'\''t get up."}'
```

```json
{
  "findings": [
    {"sign_id": "froth_nose_mouth", "value": "yes", "quote": "foam coming from her nose"},
    {"sign_id": "unable_to_stand", "value": "yes", "quote": "can't get up"}
  ],
  "escalate": true,
  "reason": "Escalation signs reported: froth_nose_mouth (yes), unable_to_stand (yes)."
}
```

Blank or missing messages return `422`. Provider failures and unusable model
output return `502` with a generic message; keys and provider response bodies
are never echoed back.

## Tests

```bash
uv run pytest          # offline: the LLM is mocked, no key or network needed
uv run pytest -m live  # opt-in, calls the real provider (needs LLM_API_KEY)
```

The default suite covers the five sample messages, the escalation truth table,
and the validator's rejection paths (unknown sign ID, bad value, hallucinated
quote, bad JSON, blank message). The `live` tests are skipped unless a key is
set, so they never break CI.

## Decisions

- **One OpenAI-compatible adapter.** It covers OpenAI, Groq's free tier,
  OpenRouter, Ollama and Gemini's compatibility endpoint with no extra
  dependency. Adding a native provider SDK would only be worth it if a specific
  model's structured-output mode proved materially better.
- **The model proposes, validation disposes.** The LLM returns JSON; Pydantic
  and a small validation pass enforce the contract. Unknown `sign_id`s, invalid
  values, and non-string fields are dropped rather than failing the whole
  request, because one bad item should not lose the other real findings. A
  malformed top-level payload is a `502`.
- **Quotes must be real.** Every quote is checked as a case-insensitive,
  whitespace-normalised substring of the message. This enforces "only report
  signs the message actually mentions" and makes hallucinated evidence visible
  and discardable. The trade-off: a paraphrasing model loses a true finding.
  That is the safe direction for triage, but it is the first policy to revisit
  after a live evaluation.
- **`no` means explicit denial, not silence.** A finding with value `no` is
  only emitted when the farmer denies the sign ("no foam"). Unmentioned signs
  are absent from `findings` entirely. This keeps `not_sure` and `no`
  distinct and stops the model from filling the list with implicit negatives.
- **`not_sure` belongs to the farmer.** "Not eating" is `reduced_appetite:
  yes`; `not_sure` is reserved for the farmer's own hedging ("I think... but
  I'm not sure").
- **Duplicates keep the strongest value** (`yes > not_sure > no`) and output is
  sorted in catalogue order so responses are deterministic.
- **Escalation is plain code, not a prompt.** `app/triage.py` is the single
  auditable rule: `froth_nose_mouth`, `unable_to_stand`, or `cloudy_eye` at
  `yes` or `not_sure` escalates. The reason string names the triggers.
- **Shona/Ndebele is handled in the prompt, not a translation step.** The sign
  list includes `mbandabvu` and the prompt explains phrases such as
  *haisi kudya*. Translating first would add latency and its own error mode;
  modern models handle the common code-mixing seen in the samples.
- **Single message, stateless.** The endpoint has no conversation memory, so it
  cannot use earlier WhatsApp turns. That is a real limitation, not an
  oversight, and is the first thing to add for production.
- **No retries or model fallback in v1.** A failed call is a `502`; retrying
  silently inside a triage path would double latency and hide provider
  problems. Retry with backoff belongs at the caller or a later iteration.

## How I would measure extraction accuracy

1. **Gold set.** Collect real WhatsApp messages (with consent and PII removed),
   stratified by sign, explicit negation, uncertainty, mixed Shona/Ndebele,
   message length, and "nothing wrong" cases. Have at least two clinicians or
   veterinary officers label each sign as `yes` / `no` / `not_sure`, or
   `not_mentioned`. Report inter-annotator agreement (Cohen's kappa) so we know
   the ceiling; ambiguous messages should be adjudicated.
2. **Per-sign metrics.** For each of the nine signs, precision, recall and F1,
   treating "not mentioned" as absence. Per-sign recall matters more than a
   single aggregate because the signs differ hugely in prevalence.
3. **Quote attribution.** Fraction of returned quotes that are genuine
   substrings and actually support the label (human-checked sample). This
   catches a model that gets the label right for the wrong reason.
4. **Escalation confusion matrix.** Escalate/not-escalate against the clinician
   gold label, with **escalation recall as the headline metric**. A missed
   escalation is the costly error; a false alarm costs a phone call. I would
   target ≥ 0.98 recall on the urgent signs and track the false-positive rate
   separately.
5. **Uncertainty calibration.** How often `not_sure` is used, and whether it
   correlates with human disagreement or genuinely ambiguous messages. Too
   much `not_sure` makes triage useless; too little hides risk.
6. **Slices and error analysis.** Break results down by language mix, negation,
   message length, and sign combination. Read every failure; categorise them
   (missed paraphrase, over-inference, quote drift, negation error, translation
   error) and turn the frequent ones into prompt/eval cases.
7. **Online monitoring.** Sample production extractions for clinician review,
   track escalation overrides and downstream outcomes, and watch latency, cost,
   and provider/model versions. Re-run the gold set whenever the prompt, model,
   or provider changes.
8. **Not just LLM-as-judge.** An LLM judge can triage review effort, but the
   ground truth and the ship/no-ship decision should come from labelled data
   and clinician review.

The five sample messages are a smoke test, not an accuracy measurement. The
live suite was run against OpenRouter with `google/gemini-2.5-flash` and all
five produced the expected findings and escalation flags. The real evaluation
still needs the labelled set above.

## What I would do with more time

- Build the labelled gold set and an evaluation harness that reports the
  metrics above, runnable in CI on every prompt/model change.
- Add conversation context: WhatsApp threads often spread symptoms over several
  messages, and "she is still like that" is meaningless in isolation.
- Add retry with backoff plus a fallback model, and structured/JSON-schema
  decoding where the provider supports it, to reduce malformed output.
- Improve negation and scope handling ("she is eating, but no longer drinking",
  "the calf is fine" should not generate implicit negatives).
- Test native Shona and Ndebele messages with first-language reviewers, rather
  than relying on the English prompt glossary.
- Add confidence/abstention and route low-confidence or ambiguous cases to a
  human, with a review queue.
- Operational concerns: auth/rate limiting on the endpoint, request logging
  with PII redaction, prompt versioning, caching identical messages, metrics
  and tracing, and a cost/latency budget per extraction.
- Consider a smaller/faster model for the common cases and escalate only hard
  messages to a larger model, measured against the gold set.

## How AI was used

I used the OpenCode coding agent to scaffold the project write , tests. I reviewed
the code and made the product decisions above: the validation and
drop-versus-fail policy, quote verification, `no`/`not_sure` semantics,
deduplication, and keeping escalation in plain code. All code is intended to be
walked through line by line in the interview.

The offline suite uses mocked model output, which verifies the plumbing and the
safety rules. The live suite was run against OpenRouter with
`google/gemini-2.5-flash`: all five sample messages passed. That is still a
smoke test, not an accuracy measurement; the prompt should be validated against
the labelled gold set before production use.
