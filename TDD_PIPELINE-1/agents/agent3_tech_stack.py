"""Section 3 -- Tech Stack, optional. Tier 2."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """This section only applies if nfr_triggered is true.

RULES:
1. If nfr_triggered is false, set applicable to false, numeric_target_missing
   to false, stack to an empty array, and state in decisions_made: "No NFR
   target in FDD -- uses existing application stack, no new infrastructure
   justified."
2. Before recommending anything, check whether performance_target or
   concurrency_note contains an ACTUAL number (a time unit like "5
   minutes" or "200ms", a percentage, a request count, or similar). Words
   like "real-time," "fast," "scalable," "competitive," or "simultaneous"
   are NOT numbers, even though they imply urgency or scale.
3. If NO actual number is present anywhere in the input, set
   numeric_target_missing to true. In this case:
   - Do not prescribe a specific multi-layer architecture as if it were
     required.
   - Name only the general CAPABILITY CLASS the vague wording might
     imply (e.g. "some form of low-latency data access" rather than
     "distributed cache with Redis/Memcached").
   - Add this exact caveat to decisions_made: "FDD gives no quantified
     latency/throughput number -- this is a provisional, capability-level
     suggestion pending a concrete SLA from stakeholders, not a
     requirement derived from the FDD."
4. If a real number IS present, you may recommend specific technology
   classes and products with normal confidence, citing the exact number
   as justification.
5. Never pick a specific named product (Kafka, Redis, a named database)
   unless the citation genuinely requires that class of tool. If a
   generic "a message queue" would satisfy it, log the specific product
   choice as a decision, not as if the FDD dictated that exact product.
6. Never name a layer "cache," "caching," or "fast-access store" for
   data whose current value must always be served (e.g. the live price
   or seat count this same story requires to be real-time/competitive).
   That is a contradiction with any caching-strategy section evaluating
   the same performance_target, which will correctly reject caching for
   exactly this data. If low-latency access to the CURRENT value is
   needed, name it a "current-state store" or "hot-path read path" with
   no TTL and no staleness window -- a fast store is not automatically a
   cache. Reserve "cache"/TTL language only for data that is genuinely
   allowed to lag behind the source of truth.

SELF-CHECK: quote the exact substring from performance_target or
concurrency_note that contains a number, before writing any stack entry.
If you cannot quote one, numeric_target_missing must be true and your
stack must stay at the capability-class level, not a full architecture.

Output strict JSON: applicable (boolean), numeric_target_missing
(boolean), stack (array of {layer, choice, justification}), decisions_made
(array). JSON only."""


def run(state: dict) -> dict:
    section12 = (state.get("fdd_sections") or {}).get("12") or {}
    payload = {
        "nfr_triggered": section12.get("triggered", False),
        "performance_target": section12.get("performance_target"),
        "concurrency_note": section12.get("concurrency_note"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "3", "agent3_tech_stack", result)