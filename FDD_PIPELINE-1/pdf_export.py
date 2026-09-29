"""Render an FDD markdown file as a structured PDF.

JSON fences in the markdown are parsed and laid out as labeled fields,
tables, lists, and cards -- not pasted as raw JSON.
"""
import json
import re

from fpdf import FPDF
from fpdf.enums import VAlign, XPos, YPos
from fpdf.fonts import FontFace

NAVY = (18, 42, 84)
ACCENT = (36, 99, 168)
INK = (32, 36, 42)
MUTED = (95, 104, 115)
LINE = (220, 226, 234)
BAND = (18, 42, 84)
ROW_ALT = (246, 248, 252)
ASSUME_BG = (255, 249, 235)
ASSUME_BORDER = (232, 201, 120)
NA_BG = (244, 246, 248)
CARD_BG = (247, 249, 252)
WHITE = (255, 255, 255)


def _plain(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    return text


def _pdf_text(text) -> str:
    if text is None:
        return "-"
    if isinstance(text, bool):
        return "Yes" if text else "No"
    text = str(text)
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2022": "-",
        "\u00a0": " ",
        "\u2026": "...",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def _label(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _is_blank(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


class FddPdf(FPDF):
    def __init__(self):
        super().__init__(format="Letter")
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(16, 18, 16)
        self._cover_done = False

    def header(self):
        if self.page_no() == 1 and not self._cover_done:
            return
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 11, "F")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*WHITE)
        self.set_xy(16, 3)
        self.cell(120, 5, "Functional Design Document")
        self.cell(0, 5, "Confidential draft", align="R")
        self.set_y(16)
        self.set_text_color(*INK)

    def footer(self):
        self.set_y(-14)
        self.set_draw_color(*LINE)
        self.set_line_width(0.3)
        self.line(16, self.get_y(), self.w - 16, self.get_y())
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")
        self.set_text_color(*INK)

    @property
    def usable(self) -> float:
        return self.w - self.l_margin - self.r_margin

    def ensure(self, height: float) -> None:
        if self.will_page_break(height):
            self.add_page()

    def cover(self, title: str, subtitle: str) -> None:
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 52, "F")
        self.set_xy(16, 16)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(180, 205, 235)
        self.cell(0, 6, "FUNCTIONAL DESIGN DOCUMENT")
        self.ln(8)
        self.set_x(16)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(*WHITE)
        self.multi_cell(0, 9, _pdf_text(title))
        if subtitle:
            self.set_x(16)
            self.set_font("Helvetica", "", 11)
            self.set_text_color(210, 222, 240)
            self.multi_cell(0, 6, _pdf_text(subtitle))
        self.set_y(60)
        self.set_text_color(*INK)
        self._cover_done = True

    def toc(self, sections: list[dict]) -> None:
        self.subhead("Contents")
        for section in sections:
            heading = section["heading"]
            note = "  - not applicable" if section.get("skipped") else ""
            self.set_font("Helvetica", "", 10)
            self.set_text_color(*MUTED if note else INK)
            self.cell(
                0,
                6,
                _pdf_text(heading + note),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
        self.set_text_color(*INK)
        self.ln(4)

    def section_banner(self, heading: str) -> None:
        self.ensure(16)
        self.ln(2)
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 12)
        self.cell(0, 9, f"  {_pdf_text(heading)}", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)
        self.set_text_color(*INK)

    def subhead(self, text: str) -> None:
        self.ensure(12)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*NAVY)
        self.cell(0, 6, _pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        y = self.get_y()
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.6)
        self.line(self.l_margin, y, self.l_margin + 28, y)
        self.ln(3)
        self.set_text_color(*INK)

    def kv(self, label: str, value, indent: float = 0) -> None:
        if _is_blank(value) and not isinstance(value, bool):
            value = "-"
        self.ensure(14)
        self.set_x(self.l_margin + indent)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*ACCENT)
        self.cell(0, 4.5, _pdf_text(label.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_x(self.l_margin + indent)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*INK)
        self.multi_cell(self.usable - indent, 5, _pdf_text(value))
        self.ln(1.5)

    def bullets(self, items: list, indent: float = 0) -> None:
        if not items:
            self.set_font("Helvetica", "I", 10)
            self.set_text_color(*MUTED)
            self.set_x(self.l_margin + indent)
            self.cell(0, 5, "None identified.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_text_color(*INK)
            self.ln(1)
            return
        for item in items:
            self.ensure(8)
            x = self.l_margin + indent
            y = self.get_y()
            self.set_fill_color(*ACCENT)
            self.ellipse(x + 1.2, y + 1.7, 1.6, 1.6, "F")
            self.set_xy(x + 6, y)
            self.set_font("Helvetica", "", 10)
            self.set_text_color(*INK)
            self.multi_cell(self.usable - indent - 6, 5, _pdf_text(item))
        self.ln(1)

    def numbered(self, items: list) -> None:
        if not items:
            self.bullets([])
            return
        for i, item in enumerate(items, start=1):
            self.ensure(8)
            y = self.get_y()
            self.set_xy(self.l_margin, y)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*ACCENT)
            self.cell(10, 5, f"{i}.")
            self.set_xy(self.l_margin + 10, y)
            self.set_font("Helvetica", "", 10)
            self.set_text_color(*INK)
            self.multi_cell(
                self.usable - 10,
                5,
                _pdf_text(item),
                new_x=XPos.LMARGIN,
                new_y=YPos.NEXT,
            )
        self.ln(1)

    def na_banner(self, message: str) -> None:
        self.ensure(14)
        self.set_fill_color(*NA_BG)
        self.set_text_color(*MUTED)
        self.set_font("Helvetica", "I", 10)
        self.multi_cell(0, 8, f"  {_pdf_text(message)}", fill=True)
        self.set_text_color(*INK)
        self.ln(3)

    def assumption_box(self, items: list) -> None:
        if not items:
            return
        self.subhead("Assumptions")
        self.ensure(10)
        start = self.get_y()
        self.set_fill_color(*ASSUME_BG)
        # Write first so we know height, then... just fill each line.
        for item in items:
            self.ensure(8)
            y = self.get_y()
            self.set_fill_color(*ASSUME_BG)
            self.set_x(self.l_margin)
            self.set_font("Helvetica", "", 9)
            self.set_text_color(90, 70, 20)
            self.multi_cell(self.usable, 4.8, f"-  {_pdf_text(item)}", fill=True)
        self.set_draw_color(*ASSUME_BORDER)
        self.set_line_width(0.4)
        self.line(self.l_margin, start, self.l_margin, self.get_y())
        self.set_text_color(*INK)
        self.ln(3)

    def two_col_kv(self, pairs: list[tuple[str, object]]) -> None:
        usable = self.usable
        col_w = (usable - 4) / 2
        i = 0
        while i < len(pairs):
            self.ensure(16)
            y = self.get_y()
            left_label, left_val = pairs[i]
            self._mini_kv(self.l_margin, y, col_w, left_label, left_val)
            h1 = self.get_y() - y
            self.set_y(y)
            if i + 1 < len(pairs):
                right_label, right_val = pairs[i + 1]
                self._mini_kv(self.l_margin + col_w + 4, y, col_w, right_label, right_val)
                h2 = self.get_y() - y
            else:
                h2 = 0
            self.set_y(y + max(h1, h2) + 2)
            i += 2

    def _mini_kv(self, x, y, w, label, value) -> None:
        self.set_xy(x, y)
        self.set_fill_color(*ROW_ALT)
        self.set_font("Helvetica", "B", 7.5)
        self.set_text_color(*ACCENT)
        self.cell(w, 5, f"  {_pdf_text(label.upper())}", fill=True, new_x=XPos.LEFT, new_y=YPos.NEXT)
        self.set_x(x)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*INK)
        display = "-" if _is_blank(value) and not isinstance(value, bool) else value
        self.multi_cell(w, 5.2, f"  {_pdf_text(display)}", fill=True)

    def card(self, title: str, fields: list[tuple[str, object]], accent=ACCENT) -> None:
        width = self.usable
        inner = width - 8
        # Estimate height
        self.set_font("Helvetica", "B", 10)
        title_lines = self.multi_cell(inner, 5.5, _pdf_text(title), dry_run=True, output="LINES")
        h = 8 + len(title_lines) * 5.5
        for label, value in fields:
            if _is_blank(value) and not isinstance(value, bool):
                continue
            self.set_font("Helvetica", "B", 7.5)
            h += 4.4
            self.set_font("Helvetica", "", 9.5)
            body_lines = self.multi_cell(
                inner, 4.8, _pdf_text(value), dry_run=True, output="LINES"
            )
            h += max(1, len(body_lines)) * 4.8 + 1.5
        h += 4
        self.ensure(min(h, 40))
        y = self.get_y()
        if self.will_page_break(h):
            self.add_page()
            y = self.get_y()
        self.set_fill_color(*CARD_BG)
        self.rect(self.l_margin, y, width, h, "F")
        self.set_fill_color(*accent)
        self.rect(self.l_margin, y, 2.4, h, "F")
        self.set_xy(self.l_margin + 6, y + 3)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*NAVY)
        self.multi_cell(inner, 5.5, _pdf_text(title))
        for label, value in fields:
            if _is_blank(value) and not isinstance(value, bool):
                continue
            self.set_x(self.l_margin + 6)
            self.set_font("Helvetica", "B", 7.5)
            self.set_text_color(*ACCENT)
            self.cell(inner, 4.4, _pdf_text(label.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.set_x(self.l_margin + 6)
            self.set_font("Helvetica", "", 9.5)
            self.set_text_color(*INK)
            self.multi_cell(inner, 4.8, _pdf_text(value))
            self.ln(0.6)
        self.set_y(y + h + 3)
        self.set_text_color(*INK)

    def simple_table(self, headers: list[str], rows: list[list[str]], col_widths) -> None:
        if not rows:
            self.bullets([])
            return
        heading_style = FontFace(
            emphasis="BOLD",
            color=WHITE,
            fill_color=NAVY,
            size_pt=8,
        )
        self.ensure(16)
        with self.table(
            width=self.usable,
            col_widths=col_widths,
            line_height=4.8,
            text_align="LEFT",
            align="LEFT",
            headings_style=heading_style,
            first_row_as_headings=True,
            v_align=VAlign.T,
            markdown=False,
        ) as table:
            head = table.row()
            for header in headers:
                head.cell(_pdf_text(header))
            for i, values in enumerate(rows):
                row = table.row(style=FontFace(fill_color=ROW_ALT if i % 2 else WHITE))
                for value in values:
                    row.cell(_pdf_text(value or "-"))
        self.ln(3)

    def render_data(self, data: dict) -> None:
        if not isinstance(data, dict):
            self.kv("Value", data)
            return
        if data.get("triggered") is False:
            self.na_banner("Not applicable to this story -- evaluated and excluded by its agent.")
            return

        assumptions = data.get("assumptions_made")
        payload = {k: v for k, v in data.items() if k != "assumptions_made"}

        if "document_id" in payload:
            self._render_metadata(payload)
        elif "parsed_clauses" in payload or "business_objective" in payload:
            self._render_summary(payload)
        elif "pre_conditions" in payload or "post_conditions" in payload:
            self._render_conditions(payload)
        elif "requirements" in payload:
            self._render_requirements(payload)
        elif "happy_path" in payload or "exception_paths" in payload:
            self._render_flow(payload)
        elif "fields" in payload:
            self._render_fields(payload)
        elif "internal_dependencies" in payload or "external_dependencies" in payload:
            self._render_deps(payload)
        elif "logic_gaps" in payload or "risks" in payload:
            self._render_gaps(payload)
        elif "error_matrix" in payload:
            self._render_errors(payload)
        elif "scenarios" in payload:
            self._render_scenarios(payload)
        elif "performance_target" in payload or "concurrency_note" in payload:
            self._render_nfr(payload)
        elif "localization_notes" in payload or "compliance_notes" in payload:
            self._render_compliance(payload)
        elif "rollout_strategy_options" in payload or "migration_needed" in payload:
            self._render_cutover(payload)
        else:
            self._render_generic(payload)

        if isinstance(assumptions, list):
            self.assumption_box(assumptions)

    def _render_metadata(self, data: dict) -> None:
        self.two_col_kv(
            [
                ("Document ID", data.get("document_id")),
                ("Version", data.get("version")),
                ("Target Release", data.get("target_release")),
            ]
        )
        approvers = data.get("approvers") or {}
        if isinstance(approvers, dict):
            self.subhead("Approvers")
            self.two_col_kv(
                [
                    ("Engineering", approvers.get("engineering")),
                    ("QA", approvers.get("qa")),
                    ("PM", approvers.get("pm")),
                ]
            )
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"document_id", "version", "target_release", "approvers"}
        }
        self._render_generic(leftover)

    def _render_summary(self, data: dict) -> None:
        clauses = data.get("parsed_clauses") or {}
        if isinstance(clauses, dict) and any(clauses.values()):
            self.subhead("User Story")
            mapping = [
                ("As a", clauses.get("as_a")),
                ("I want", clauses.get("i_want")),
                ("So that", clauses.get("so_that")),
            ]
            for label, value in mapping:
                if value:
                    self.kv(label, value)
        if data.get("business_objective"):
            self.subhead("Business Objective")
            self.set_font("Helvetica", "", 10)
            self.multi_cell(0, 5.2, _pdf_text(data["business_objective"]))
            self.ln(2)
        persona = data.get("persona_definition")
        if isinstance(persona, dict):
            self.subhead("Persona")
            for key, value in persona.items():
                self.kv(_label(key), value)
        elif persona:
            self.kv("Persona", persona)
        if "in_scope" in data:
            self.subhead("In Scope")
            self.bullets(data.get("in_scope") or [])
        if "out_of_scope" in data:
            self.subhead("Out of Scope")
            self.bullets(data.get("out_of_scope") or [])
        leftover = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "parsed_clauses",
                "business_objective",
                "persona_definition",
                "in_scope",
                "out_of_scope",
            }
        }
        self._render_generic(leftover)

    def _render_conditions(self, data: dict) -> None:
        self.subhead("Pre-Conditions")
        self.bullets(data.get("pre_conditions") or [])
        self.subhead("Post-Conditions")
        self.bullets(data.get("post_conditions") or [])
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"pre_conditions", "post_conditions"}
        }
        self._render_generic(leftover)

    def _render_requirements(self, data: dict) -> None:
        reqs = data.get("requirements") or []
        self.subhead(f"Requirements ({len(reqs)})")
        for req in reqs:
            if not isinstance(req, dict):
                self.bullets([req])
                continue
            req_id = req.get("req_id") or "Requirement"
            feature = req.get("feature") or req.get("actor_or_component") or ""
            title = f"{req_id}  |  {feature}" if feature else str(req_id)
            self.card(
                title,
                [
                    ("The system shall", req.get("shall_statement")),
                    ("UI copy / message", req.get("ui_copy_or_message")),
                ],
            )
        leftover = {k: v for k, v in data.items() if k != "requirements"}
        self._render_generic(leftover)

    def _render_flow(self, data: dict) -> None:
        path = data.get("happy_path") or []
        self.subhead("Happy Path")
        if path and all(isinstance(item, str) for item in path):
            self.ensure(10)
            self.set_font("Helvetica", "", 10)
            self.set_text_color(*INK)
            self.multi_cell(0, 6, _pdf_text("  ->  ".join(path)))
            self.ln(2)
        else:
            self.numbered(path)
        alts = data.get("alternative_paths") or []
        self.subhead("Alternative Paths")
        if alts and isinstance(alts[0], dict):
            for alt in alts:
                self.card(
                    alt.get("name") or "Alternative",
                    [( _label(k), v) for k, v in alt.items() if k != "name"],
                )
        else:
            self.bullets(alts)
        exceptions = data.get("exception_paths") or []
        self.subhead("Exception Paths")
        if exceptions and isinstance(exceptions[0], dict):
            rows = [
                [
                    item.get("failure_scenario") or "",
                    item.get("system_behavior") or "",
                ]
                for item in exceptions
            ]
            self.simple_table(
                ["Failure scenario", "System behavior"],
                rows,
                (45, 55),
            )
        else:
            self.bullets(exceptions)
        transitions = data.get("state_transitions") or []
        self.subhead("State Transitions")
        if transitions and isinstance(transitions[0], dict):
            rows = []
            for item in transitions:
                rows.append(
                    [
                        item.get("from") or item.get("from_state") or "",
                        item.get("to") or item.get("to_state") or "",
                        item.get("trigger") or item.get("event") or item.get("condition") or "",
                    ]
                )
            self.simple_table(["From", "To", "Trigger"], rows, (25, 25, 50))
        else:
            self.bullets(transitions)
        leftover = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "happy_path",
                "alternative_paths",
                "exception_paths",
                "state_transitions",
            }
        }
        self._render_generic(leftover)

    def _render_fields(self, data: dict) -> None:
        fields = data.get("fields") or []
        self.subhead(f"Data Fields ({len(fields)})")
        rows = []
        for field in fields:
            if not isinstance(field, dict):
                rows.append([str(field), "", "", ""])
                continue
            rules = field.get("validation_rules") or []
            if isinstance(rules, list):
                rules_txt = "; ".join(str(r) for r in rules)
            else:
                rules_txt = str(rules)
            rows.append(
                [
                    (field.get("field_name") or "").replace("_", " "),
                    field.get("data_type") or "",
                    (field.get("persistence") or "").replace("_", " "),
                    rules_txt,
                ]
            )
        self.simple_table(
            ["Field", "Type", "Persistence", "Validation"],
            rows,
            (24, 14, 24, 38),
        )
        leftover = {k: v for k, v in data.items() if k != "fields"}
        self._render_generic(leftover)

    def _render_deps(self, data: dict) -> None:
        self.subhead("Internal Dependencies")
        self.bullets(data.get("internal_dependencies") or [])
        self.subhead("External Dependencies")
        self.bullets(data.get("external_dependencies") or [])
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"internal_dependencies", "external_dependencies"}
        }
        self._render_generic(leftover)

    def _render_gaps(self, data: dict) -> None:
        gaps = data.get("logic_gaps") or []
        self.subhead(f"Logic Gaps ({len(gaps)})")
        for gap in gaps:
            if not isinstance(gap, dict):
                self.bullets([gap])
                continue
            phrase = gap.get("vague_phrase") or "Gap"
            self.card(
                f'"{phrase}"',
                [
                    ("Location", gap.get("location")),
                    ("What needs a decision", gap.get("gap_description")),
                ],
                accent=(168, 84, 36),
            )
        grouped = data.get("consolidated_assumptions") or []
        if grouped:
            self.subhead("Consolidated Assumptions")
            for group in grouped:
                if isinstance(group, dict):
                    self.set_font("Helvetica", "B", 10)
                    self.set_text_color(*NAVY)
                    self.cell(
                        0,
                        6,
                        _pdf_text(group.get("category") or "Assumptions"),
                        new_x=XPos.LMARGIN,
                        new_y=YPos.NEXT,
                    )
                    self.set_text_color(*INK)
                    self.bullets(group.get("assumptions") or [], indent=2)
                else:
                    self.bullets([group])
        risks = data.get("risks") or []
        self.subhead(f"Risks ({len(risks)})")
        for risk in risks:
            if not isinstance(risk, dict):
                self.bullets([risk])
                continue
            self.card(
                "Risk",
                [
                    ("If this is wrong", risk.get("risk")),
                    ("Mitigation", risk.get("mitigation")),
                ],
                accent=(153, 40, 40),
            )
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"logic_gaps", "consolidated_assumptions", "risks"}
        }
        self._render_generic(leftover)

    def _render_errors(self, data: dict) -> None:
        matrix = data.get("error_matrix") or []
        self.subhead("Error Handling Matrix")
        if matrix and isinstance(matrix[0], dict):
            rows = [
                [
                    item.get("scenario") or "",
                    item.get("user_facing_behavior") or "",
                ]
                for item in matrix
            ]
            self.simple_table(["Scenario", "What the user sees"], rows, (40, 60))
        else:
            self.bullets(matrix)
        leftover = {k: v for k, v in data.items() if k != "error_matrix"}
        self._render_generic(leftover)

    def _render_scenarios(self, data: dict) -> None:
        scenarios = data.get("scenarios") or []
        if "reconciled_with_existing_ac" in data:
            self.kv(
                "Reconciled with story acceptance criteria",
                data.get("reconciled_with_existing_ac"),
            )
        self.subhead(f"Scenarios ({len(scenarios)})")
        for i, sc in enumerate(scenarios, start=1):
            if not isinstance(sc, dict):
                self.bullets([sc])
                continue
            self.card(
                f"{i}.  {sc.get('name') or 'Scenario'}",
                [
                    ("Given", sc.get("given")),
                    ("When", sc.get("when")),
                    ("Then", sc.get("then")),
                ],
            )
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"scenarios", "reconciled_with_existing_ac"}
        }
        self._render_generic(leftover)

    def _render_nfr(self, data: dict) -> None:
        self.kv("Performance", data.get("performance_target"))
        self.kv("Concurrency", data.get("concurrency_note"))
        self.kv("Retention", data.get("retention_note"))
        leftover = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "triggered",
                "performance_target",
                "concurrency_note",
                "retention_note",
            }
        }
        self._render_generic(leftover)

    def _render_compliance(self, data: dict) -> None:
        self.subhead("Localization")
        self.bullets(data.get("localization_notes") or [])
        self.subhead("Compliance")
        self.bullets(data.get("compliance_notes") or [])
        self.subhead("Accessibility")
        self.bullets(data.get("accessibility_notes") or [])
        leftover = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "triggered",
                "localization_notes",
                "compliance_notes",
                "accessibility_notes",
            }
        }
        self._render_generic(leftover)

    def _render_cutover(self, data: dict) -> None:
        self.kv("Migration needed", data.get("migration_needed"))
        if data.get("migration_notes"):
            self.kv("Migration notes", data.get("migration_notes"))
        self.subhead("Rollout options")
        self.bullets(data.get("rollout_strategy_options") or [])
        if data.get("kill_switch_note"):
            self.kv("Kill switch", data.get("kill_switch_note"))
        leftover = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "migration_needed",
                "migration_notes",
                "rollout_strategy_options",
                "kill_switch_note",
            }
        }
        self._render_generic(leftover)

    def _render_generic(self, data) -> None:
        if _is_blank(data):
            return
        if isinstance(data, dict):
            for key, value in data.items():
                if key == "triggered":
                    continue
                if isinstance(value, list):
                    self.subhead(_label(key))
                    if value and isinstance(value[0], dict):
                        for item in value:
                            title = (
                                item.get("name")
                                or item.get("title")
                                or item.get("req_id")
                                or _label(key)
                            )
                            fields = [
                                (_label(k), v)
                                for k, v in item.items()
                                if k not in {"name", "title", "req_id"}
                            ]
                            self.card(str(title), fields)
                    else:
                        self.bullets(value)
                elif isinstance(value, dict):
                    self.subhead(_label(key))
                    for inner_k, inner_v in value.items():
                        if isinstance(inner_v, (list, dict)):
                            self._render_generic({inner_k: inner_v})
                        else:
                            self.kv(_label(inner_k), inner_v)
                else:
                    self.kv(_label(key), value)
        elif isinstance(data, list):
            self.bullets(data)
        else:
            self.kv("Value", data)


def _parse_markdown(source: str) -> tuple[str, str, list[dict]]:
    title = "Functional Design Document"
    subtitle = ""
    sections: list[dict] = []
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            heading = line[3:].strip()
            body: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].startswith("## "):
                body.append(lines[i])
                i += 1
            i -= 1
            blob = "\n".join(body).strip()
            data = None
            skipped = None
            fence = re.search(r"```json\s*(.*?)\s*```", blob, re.S)
            if fence:
                data = json.loads(fence.group(1))
            else:
                cleaned = blob.strip().strip("_").strip()
                if cleaned:
                    skipped = cleaned
            sections.append({"heading": heading, "data": data, "skipped": skipped})
        elif line.startswith("*") and not subtitle:
            subtitle = _plain(line.strip())
        i += 1
    return title, subtitle, sections


def markdown_to_pdf(md_path: str, pdf_path: str) -> None:
    with open(md_path, encoding="utf-8") as f:
        source = f.read()

    title, subtitle, sections = _parse_markdown(source)
    pdf = FddPdf()
    pdf.add_page()
    pdf.cover(title, subtitle)
    pdf.toc(sections)

    for section in sections:
        pdf.section_banner(section["heading"])
        if section.get("skipped"):
            pdf.na_banner(section["skipped"])
        elif section.get("data") is not None:
            pdf.render_data(section["data"])
        else:
            pdf.na_banner("No content generated for this section.")

    pdf.output(pdf_path)
