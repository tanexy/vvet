from .schemas import Finding
from .signs import URGENT_SIGNS


def decide_escalation(findings: list[Finding]) -> tuple[bool, str]:
    """Escalation is deliberately plain code so it is auditable and testable."""
    triggers = [
        finding
        for finding in findings
        if finding.sign_id in URGENT_SIGNS and finding.value in ("yes", "not_sure")
    ]
    if not triggers:
        return False, "No escalation signs reported."

    described = ", ".join(f"{f.sign_id} ({f.value})" for f in triggers)
    return True, f"Escalation signs reported: {described}."
