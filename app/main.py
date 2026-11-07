from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException

from .extractor import ExtractionError, extract
from .llm import LLMError, call_llm
from .schemas import ExtractRequest, ExtractResponse
from .triage import decide_escalation

app = FastAPI(title="V-Vet symptom extraction", version="0.1.0")


def get_llm() -> Callable[[list[dict]], str]:
    return call_llm


@app.post("/extract", response_model=ExtractResponse)
def extract_endpoint(
    body: ExtractRequest,
    llm: Callable[[list[dict]], str] = Depends(get_llm),
) -> ExtractResponse:
    try:
        findings = extract(body.message, llm)
    except (LLMError, ExtractionError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    escalate, reason = decide_escalation(findings)
    return ExtractResponse(findings=findings, escalate=escalate, reason=reason)
