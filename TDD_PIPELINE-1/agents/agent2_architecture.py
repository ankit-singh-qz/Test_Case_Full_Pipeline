"""Section 2 -- Component Topology & Architecture. Tier 1 (parallel with 1, 4, 12)."""
from llm import call_agent
from agents.common import merge_section

SYSTEM_PROMPT = """You design component architecture from FDD requirements and dependencies
ONLY -- do not add a component "because it's standard practice."

RULES:
1. Requirements may tag each entry with either "actor_or_component" or
   "feature" as the category key -- treat both the same way: as a
   CATEGORY LABEL describing what kind of behavior it is, not a service
   name.
2. Every component you output must be one of:
   (a) a name that appears verbatim in internal_dependencies or
       external_dependencies, or
   (b) if no requirement/category maps to a named dependency, a single
       generic component called "The System".
3. NEVER turn a category label into a new capitalized proper-noun
   service name. For example: a requirement labeled "seat management" or
   with actor "seat management" does NOT justify inventing a component
   called "Seat Availability Manager" -- that name exists nowhere in the
   input. Group that requirement under whichever named dependency
   actually handles it (e.g. "Booking system", if that's the closest
   match), or under "The System" if no dependency fits.
4. If every requirement used "the system" as its actor/feature and there
   is only one or two named dependencies, output only those few
   components -- do not multiply them into a diagram that looks more
   detailed than the input supports.
5. Do not add an API gateway, WAF, load balancer, or cache tier unless a
   requirement or dependency specifically implies one.
6. data_flow: only include a hop between two components you just listed
   in steps 2-4.

SELF-CHECK before you output: for every component name you wrote, search
for that EXACT string in internal_dependencies or external_dependencies.
If you cannot find it verbatim there (and it isn't "The System"), you
invented it -- remove it and reassign that requirement to a dependency
that IS named in the input, or to "The System".

Output strict JSON: components (array of {name, justified_by}), data_flow
(array of strings), decisions_made (array). JSON only."""


def run(state: dict) -> dict:
    fdd = state.get("fdd_sections") or {}
    section4 = fdd.get("4") or {}
    section7 = fdd.get("7") or {}
    payload = {
        "requirements": section4.get("requirements"),
        "internal_dependencies": section7.get("internal_dependencies"),
        "external_dependencies": section7.get("external_dependencies"),
    }
    result = call_agent(SYSTEM_PROMPT, payload)
    return merge_section(state, "2", "agent2_architecture", result)