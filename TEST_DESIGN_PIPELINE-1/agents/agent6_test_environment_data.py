"""Section 6 -- Test Environment & Data. Tier 2 (uses Agent 2 and Agent 7's
own-run output)."""
from llm import call_agent
from agents.common import CHAR_LIMIT_RULE, merge_section

SYSTEM_PROMPT = """You define what test environment and seed/test data are needed to execute
the scenarios this design will produce. You do not write scenarios here.

RULES:
1. environment_needs must be derived from: internal_dependencies /
   external_dependencies (each needs a controllable stub or a real test
   instance -- state which failure modes each stub must support, e.g.
   "delay, drop, error", only for dependencies that actually appear in
   the input), resilience_mechanisms (if present, note the ability to
   control time/clock so retry/timeout windows do not have to be waited
   out in real time), concurrency_applicable (if true, note the ability
   to fire simultaneous requests against the same entity),
   kill_switch_config_key (if present, note it must be togglable per
   test), and token_scopes/authn_authz (name the distinct test user or
   token combinations needed: one per scope, plus one expired/revoked
   session).
2. data_sets: one row per distinct data need implied by field_partitions
   (seed records covering the valid/invalid examples already derived --
   reference field_partitions, do not re-derive them), plus one row for
   any external input the dependencies imply (e.g. a feed of upstream
   events/metrics if an external_dependency describes one). Give each a
   short data_set_id (e.g. D-1, D-2) and a content description.
3. If a performance-relevant section is present but async_topic_name /
   throughput numbers are absent, add a data_set row stating the load
   profile is pending stakeholder input rather than inventing numbers.
4. Do not stub or seed data for anything in out_of_scope.

Output strict JSON: environment_needs (array of strings), data_sets
(array of {data_set_id, content}), assumptions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    tdd = state.get("tdd_sections") or {}
    section7 = fdd.get("7") or {}
    test2 = (state.get("test_sections") or {}).get("2") or {}
    test7 = (state.get("test_sections") or {}).get("7") or {}
    tdd4 = tdd.get("4") or {}
    tdd9 = tdd.get("9") or {}
    tdd11 = tdd.get("11") or {}
    tdd12 = tdd.get("12") or {}
    tdd15 = tdd.get("15") or {}
    tdd10 = tdd.get("10") or {}
    payload = {
        "internal_dependencies": section7.get("internal_dependencies"),
        "external_dependencies": section7.get("external_dependencies"),
        "field_partitions": test7.get("fields"),
        "table_name": tdd4.get("table_name"),
        "existing_table_name": tdd4.get("existing_table_name"),
        "concurrency_applicable": tdd9.get("applicable"),
        "resilience_mechanisms": tdd11.get("mechanisms"),
        "token_scopes": tdd12.get("token_scopes"),
        "authn_authz": tdd12.get("authn_authz"),
        "kill_switch_config_key": tdd15.get("config_key") if tdd15.get("applicable") else None,
        "async_topic_name": tdd10.get("topic_name") if tdd10.get("applicable") else None,
        "out_of_scope": test2.get("out_of_scope"),
    }
    result = call_agent(SYSTEM_PROMPT + CHAR_LIMIT_RULE, payload)
    return merge_section(state, "6", "agent6_test_environment_data", result)
