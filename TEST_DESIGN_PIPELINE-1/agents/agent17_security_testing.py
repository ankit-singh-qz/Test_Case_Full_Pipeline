"""Section 17 -- Security Testing (SEC) scenarios. Tier 3."""
from llm import call_agent
from agents.common import (
    BLOCKING_RULE,
    CHAR_LIMIT_RULE,
    issue_ids,
    merge_section,
    normalize_scenarios,
)

SYSTEM_PROMPT = """You write Security Testing (SEC) scenarios: authentication,
authorization, and data-protection checks.

RULES:
1. If tdd_authn_authz describes an authentication mechanism (e.g. MFA,
   session/token expiry), write one scenario per distinct authentication
   rule stated (a valid session succeeds; an expired/revoked session is
   rejected).
2. If tdd_token_scopes lists distinct scopes, write one scenario per
   scope verifying a caller WITHOUT that scope is refused on the
   matching operation, and one confirming a caller WITH only that scope
   cannot exceed it (least-privilege check) -- only for scopes actually
   listed, never invented ones.
3. If fdd_permission_denied_entries describes a permission-denied
   behavior with no defined error code in tdd_authn_authz, still write
   the scenario and state the expected behavior from the FDD text. A
   missing error code is a missing fact, not a blocker: note it in
   assumptions_made and leave blocked_by_issue null.
4. If tdd_transport_encryption or tdd_at_rest_encryption states a
   specific standard (e.g. a minimum TLS version, an at-rest cipher),
   write one scenario verifying that standard is enforced and weaker
   options are rejected (for transport), or one Inspection-technique
   scenario confirming the standard is applied (for at-rest, since a
   test cannot force weaker encryption at rest the way it can force a
   weaker TLS handshake).
5. If tdd_masking_rules is non-empty, write one scenario per rule
   verifying the masked/unmasked fields.
6. design_technique is "Equivalence Partitioning" for scope/permission
   scenarios, "Inspection" for encryption-standard verification.
7. priority: P1 for every scenario in this section -- security failures
   are release-blocking by definition of this category.
8. level: "Security".
9. scenario_id format: SEC-01, SEC-02, ...

Output strict JSON: scenarios (array of {scenario_id, title, src_refs,
design_technique, level, priority, blocked_by_issue, preconditions,
expected_result}), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd12 = (state.get("tdd_sections") or {}).get("12") or {}
    section2 = fdd.get("2") or {}
    section9 = fdd.get("9") or {}
    permission_entries = [
        e
        for e in (section9.get("error_matrix") or [])
        if isinstance(e, dict) and "permission" in (e.get("scenario") or "").lower()
    ]
    test4 = (state.get("test_sections") or {}).get("4") or {}
    test5 = (state.get("test_sections") or {}).get("5") or {}
    payload = {
        "persona_definition": section2.get("persona_definition"),
        "fdd_permission_denied_entries": permission_entries,
        "tdd_transport_encryption": tdd12.get("transport_encryption"),
        "tdd_at_rest_encryption": tdd12.get("at_rest_encryption"),
        "tdd_authn_authz": tdd12.get("authn_authz"),
        "tdd_token_scopes": tdd12.get("token_scopes"),
        "tdd_masking_rules": tdd12.get("masking_rules"),
        "issues": test4.get("issues"),
        "design_techniques": test5.get("design_techniques"),
        "prioritization_rules": test5.get("prioritization_rules"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE + BLOCKING_RULE, payload)
    result = normalize_scenarios(result, issue_ids(state))
    return merge_section(state, "17", "agent17_security_testing", result)
