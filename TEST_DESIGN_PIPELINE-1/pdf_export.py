"""Render a Test Design markdown file as a structured PDF.

JSON fences in the markdown are parsed and laid out as labeled fields,
tables, and cards -- not pasted as raw JSON. Structurally mirrors
fdd_pipeline/pdf_export.py and tdd_pipeline/pdf_export.py (same helper
class shape), but with render_data dispatch tailored to this pipeline's
own section shapes (issues log, scenario lists, traceability tables,
field partitions) instead of duplicating either of theirs.
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
ROW_ALT = (246, 248, 252)
ASSUME_BG = (255, 249, 235)
ASSUME_BORDER = (232, 201, 120)
NA_BG = (244, 246, 248)
CARD_BG = (247, 249, 252)
WHITE = (255, 255, 255)

PRIORITY_COLORS = {
    "P1": (153, 40, 40),
    "P2": (168, 120, 36),
    "P3": (95, 104, 115),
}


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


class TestDesignPdf(FPDF):
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
        self.cell(120, 5, "Test Case Design Document")
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
        self.cell(0, 6, "TEST CASE DESIGN DOCUMENT")
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

    def toc(self, sections: list) -> None:
        self.subhead("Contents")
        for section in sections:
            heading = section["heading"]
            note = "  - not applicable" if section.get("skipped") else ""
            self.set_font("Helvetica", "", 10)
            self.set_text_color(*MUTED if note else INK)
            self.cell(0, 6, _pdf_text(heading + note), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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
            self.multi_cell(self.usable - 10, 5, _pdf_text(item), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
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
        for item in items:
            self.ensure(8)
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

    def two_col_kv(self, pairs: list) -> None:
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

    def card(self, title: str, fields: list, accent=ACCENT) -> None:
        width = self.usable
        inner = width - 8
        self.set_font("Helvetica", "B", 10)
        title_lines = self.multi_cell(inner, 5.5, _pdf_text(title), dry_run=True, output="LINES")
        h = 8 + len(title_lines) * 5.5
        for label, value in fields:
            if _is_blank(value) and not isinstance(value, bool):
                continue
            self.set_font("Helvetica", "B", 7.5)
            h += 4.4
            self.set_font("Helvetica", "", 9.5)
            body_lines = self.multi_cell(inner, 4.8, _pdf_text(value), dry_run=True, output="LINES")
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

    def simple_table(self, headers: list, rows: list, col_widths) -> None:
        if not rows:
            self.bullets([])
            return
        heading_style = FontFace(emphasis="BOLD", color=WHITE, fill_color=NAVY, size_pt=8)
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
                    row.cell(_pdf_text(value if value not in (None, "") else "-"))
        self.ln(3)

    # ---- section-shape dispatch ------------------------------------

    def render_data(self, data: dict) -> None:
        if not isinstance(data, dict):
            self.kv("Value", data)
            return
        if data.get("applicable") is False:
            self.na_banner(
                "Not applicable to this feature -- evaluated and excluded by its agent."
            )
            decisions = data.get("decisions_made")
            if decisions:
                self.subhead("Why")
                self.bullets(decisions)
            assumptions = data.get("assumptions_made")
            if isinstance(assumptions, list):
                self.assumption_box(assumptions)
            return

        assumptions = data.get("assumptions_made")
        payload = {k: v for k, v in data.items() if k != "assumptions_made"}

        if "document_id" in payload:
            self._render_metadata(payload)
        elif "in_scope" in payload or "out_of_scope" in payload:
            self._render_scope(payload)
        elif "basis" in payload:
            self._render_basis(payload)
        elif "issues" in payload:
            self._render_issues(payload)
        elif "test_levels" in payload or "design_techniques" in payload:
            self._render_strategy(payload)
        elif "environment_needs" in payload or "data_sets" in payload:
            self._render_environment(payload)
        elif "fields" in payload and any(
            isinstance(f, dict) and "rule" in f for f in (payload.get("fields") or [])
        ):
            self._render_field_partitions(payload)
        elif "scenarios" in payload:
            self._render_scenarios(payload)
        elif "fr_to_scenarios" in payload:
            self._render_traceability(payload)
        elif "entry_criteria" in payload or "exit_criteria" in payload:
            self._render_criteria(payload)
        elif "next_steps" in payload:
            self._render_next_steps(payload)
        else:
            self._render_generic(payload)

        if isinstance(assumptions, list):
            self.assumption_box(assumptions)

    def _render_metadata(self, data: dict) -> None:
        self.two_col_kv(
            [
                ("Document ID", data.get("document_id")),
                ("Version", data.get("version")),
                ("Source FDD", data.get("source_fdd_id")),
                ("Source FDD Version", data.get("source_fdd_version")),
                ("Source TDD", data.get("source_tdd_id")),
                ("Source TDD Version", data.get("source_tdd_version")),
                ("Client", data.get("client_name")),
                ("Module", data.get("module_name")),
                ("Prepared By", data.get("prepared_by")),
                ("Reviewed / Approved By", data.get("reviewed_by")),
            ]
        )
        if data.get("title"):
            self.kv("Title", data.get("title"))

    def _render_scope(self, data: dict) -> None:
        self.subhead("In Scope")
        self.bullets(data.get("in_scope") or [])
        self.subhead("Out of Scope")
        self.bullets(data.get("out_of_scope") or [])

    def _render_basis(self, data: dict) -> None:
        rows = [
            [b.get("source"), b.get("used_for")]
            for b in (data.get("basis") or [])
            if isinstance(b, dict)
        ]
        self.simple_table(["Source", "Used For"], rows, (55, 115))

    def _render_issues(self, data: dict) -> None:
        issues = data.get("issues") or []
        self.subhead(f"Issues ({len(issues)})")
        for issue in issues:
            if not isinstance(issue, dict):
                self.bullets([issue])
                continue
            related = issue.get("related_sections") or {}
            related_txt = ", ".join(
                f"{doc.upper()} {', '.join(str(s) for s in sids)}"
                for doc, sids in related.items()
                if sids
            )
            self.card(
                f"{issue.get('issue_id', 'I-??')}: {issue.get('issue', '')}",
                [
                    ("Test impact", issue.get("test_impact")),
                    ("Owner", issue.get("owner_hint")),
                    ("Related sections", related_txt),
                ],
                accent=(168, 84, 36),
            )

    def _render_strategy(self, data: dict) -> None:
        levels = data.get("test_levels") or []
        if levels:
            self.subhead("Test Levels")
            rows = [[l.get("level_code"), l.get("focus")] for l in levels if isinstance(l, dict)]
            self.simple_table(["Level", "Focus"], rows, (30, 140))
        techniques = data.get("design_techniques") or []
        if techniques:
            self.subhead("Design Techniques")
            rows = [
                [t.get("technique"), t.get("applied_to")]
                for t in techniques
                if isinstance(t, dict)
            ]
            self.simple_table(["Technique", "Applied To"], rows, (45, 125))
        rules = data.get("prioritization_rules") or []
        if rules:
            self.subhead("Prioritization")
            rows = [[r.get("priority"), r.get("definition")] for r in rules if isinstance(r, dict)]
            self.simple_table(["Priority", "Definition"], rows, (20, 150))
        notes = data.get("p1_escalation_notes") or []
        if notes:
            self.subhead("P1 Escalation Notes")
            rows = [[n.get("issue_id"), n.get("note")] for n in notes if isinstance(n, dict)]
            self.simple_table(["Issue", "Note"], rows, (25, 145))

    def _render_environment(self, data: dict) -> None:
        self.subhead("Environment Needs")
        self.bullets(data.get("environment_needs") or [])
        data_sets = data.get("data_sets") or []
        if data_sets:
            self.subhead("Data Sets")
            rows = [
                [d.get("data_set_id"), d.get("content")]
                for d in data_sets
                if isinstance(d, dict)
            ]
            self.simple_table(["ID", "Content"], rows, (25, 145))

    def _render_field_partitions(self, data: dict) -> None:
        fields = data.get("fields") or []
        self.subhead(f"Fields ({len(fields)})")
        for field in fields:
            if not isinstance(field, dict):
                continue
            valid = "; ".join(str(v) for v in (field.get("valid_examples") or []))
            invalid = "; ".join(str(v) for v in (field.get("invalid_examples") or []))
            self.card(
                (field.get("field_name") or "field").replace("_", " "),
                [
                    ("Rule", field.get("rule")),
                    ("Valid examples", valid),
                    ("Invalid examples", invalid),
                    ("API exposed", field.get("api_exposed")),
                ],
            )

    def _render_scenarios(self, data: dict) -> None:
        scenarios = data.get("scenarios") or []
        self.subhead(f"Scenarios ({len(scenarios)})")
        rows = []
        for sc in scenarios:
            if not isinstance(sc, dict):
                continue
            rows.append(
                [
                    sc.get("scenario_id"),
                    sc.get("title"),
                    sc.get("design_technique"),
                    sc.get("level"),
                    sc.get("priority"),
                    sc.get("blocked_by_issue"),
                ]
            )
        self.simple_table(
            ["ID", "Title", "Technique", "Level", "Pri.", "Blocked"],
            rows,
            (16, 62, 34, 22, 12, 20),
        )
        for sc in scenarios:
            if not isinstance(sc, dict):
                continue
            self.card(
                f"{sc.get('scenario_id', '')}  {sc.get('title', '')}",
                [
                    ("Preconditions", sc.get("preconditions")),
                    ("Expected result", sc.get("expected_result")),
                    ("Source refs", sc.get("src_refs")),
                ],
                accent=PRIORITY_COLORS.get(sc.get("priority"), ACCENT),
            )
        decisions = data.get("decisions_made")
        if decisions:
            self.subhead("Notes")
            self.bullets(decisions)

    def _render_traceability(self, data: dict) -> None:
        fr_rows = [
            [r.get("req_id"), ", ".join(r.get("scenario_ids") or []) or "NONE -- gap"]
            for r in (data.get("fr_to_scenarios") or [])
            if isinstance(r, dict)
        ]
        self.subhead("Functional Requirement -> Scenarios")
        self.simple_table(["FR", "Scenarios"], fr_rows, (25, 145))

        ac_rows = [
            [r.get("acceptance_criterion"), ", ".join(r.get("scenario_ids") or []) or "NONE -- gap"]
            for r in (data.get("ac_to_scenarios") or [])
            if isinstance(r, dict)
        ]
        self.subhead("Acceptance Criterion -> Scenarios")
        self.simple_table(["AC", "Scenarios"], ac_rows, (60, 110))

        err_rows = [
            [str(r.get("error_code")), ", ".join(r.get("scenario_ids") or []) or "NONE"]
            for r in (data.get("error_code_to_scenarios") or [])
            if isinstance(r, dict)
        ]
        self.subhead("Error Code -> Scenarios")
        self.simple_table(["Code", "Scenarios"], err_rows, (25, 145))

        gaps = data.get("coverage_gaps") or []
        if gaps:
            self.subhead("Coverage Gaps")
            self.bullets(gaps)

    def _render_criteria(self, data: dict) -> None:
        self.subhead("Entry Criteria")
        self.numbered(data.get("entry_criteria") or [])
        self.subhead("Exit Criteria")
        self.numbered(data.get("exit_criteria") or [])
        self.subhead("Suspension Criteria")
        self.numbered(data.get("suspension_criteria") or [])

    def _render_next_steps(self, data: dict) -> None:
        self.numbered(data.get("next_steps") or [])

    def _render_generic(self, data) -> None:
        if _is_blank(data):
            return
        if isinstance(data, dict):
            for key, value in data.items():
                if key in {"applicable", "triggered"}:
                    continue
                if isinstance(value, list):
                    self.subhead(_label(key))
                    if value and isinstance(value[0], dict):
                        for item in value:
                            title = item.get("name") or item.get("title") or _label(key)
                            fields = [
                                (_label(k), v)
                                for k, v in item.items()
                                if k not in {"name", "title"}
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


def _parse_markdown(source: str):
    title = "Test Case Design Document"
    subtitle = ""
    sections = []
    lines = source.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            heading = line[3:].strip()
            body = []
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
            subtitle = line.strip().strip("*")
        elif line.startswith("**") and "coverage" in line.lower():
            subtitle = subtitle or ""
        i += 1
    return title, subtitle, sections


def markdown_to_pdf(md_path: str, pdf_path: str) -> None:
    with open(md_path, encoding="utf-8") as f:
        source = f.read()

    title, subtitle, sections = _parse_markdown(source)
    pdf = TestDesignPdf()
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
