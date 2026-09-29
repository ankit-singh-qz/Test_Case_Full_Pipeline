"""Render a Detailed Test Cases markdown file as a structured PDF.

JSON fences in the markdown are parsed and laid out as labeled fields,
tables, and cards -- not pasted as raw JSON. Structurally mirrors
fdd_pipeline/pdf_export.py, tdd_pipeline/pdf_export.py, and
test_design_pipeline/pdf_export.py (same helper class shape), but with
render_data dispatch tailored to this pipeline's own section shape: a
flat list of {test_case_id, scenario_id, status, steps, ...} test cases
per technique, instead of test_design_pipeline's scenario lists.
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
BLOCKED_BG = (253, 237, 237)
WHITE = (255, 255, 255)

PRIORITY_COLORS = {
    "P1": (153, 40, 40),
    "P2": (168, 120, 36),
    "P3": (95, 104, 115),
}
BLOCKED_COLOR = (153, 40, 40)


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


def _format_steps(steps) -> str:
    if not steps:
        return "-"
    lines = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        lines.append(
            f"{step.get('step_no', '?')}. {step.get('action', '')}\n"
            f"    Data: {step.get('test_data') if step.get('test_data') not in (None, '') else '-'}\n"
            f"    Expected: {step.get('expected_result', '')}"
        )
    return "\n".join(lines) if lines else "-"


class TestCasePdf(FPDF):
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
        self.cell(120, 5, "Detailed Test Cases")
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
        self.cell(0, 6, "DETAILED TEST CASES")
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

    def card(self, title: str, fields: list, accent=ACCENT, bg=CARD_BG) -> None:
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
        self.set_fill_color(*bg)
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

    # ---- section-shape dispatch ------------------------------------

    def render_data(self, data: dict) -> None:
        if not isinstance(data, dict):
            self.kv("Value", data)
            return

        assumptions = data.get("assumptions_made")
        payload = {k: v for k, v in data.items() if k != "assumptions_made"}

        if "test_cases" in payload:
            self._render_test_cases(payload)
        else:
            self._render_generic(payload)

        if isinstance(assumptions, list):
            self.assumption_box(assumptions)

    def _render_test_cases(self, data: dict) -> None:
        cases = data.get("test_cases") or []
        self.subhead(f"Test Cases ({len(cases)})")

        rows = []
        for case in cases:
            if not isinstance(case, dict):
                continue
            rows.append(
                [
                    case.get("test_case_id"),
                    case.get("scenario_id"),
                    case.get("status"),
                    case.get("priority"),
                    case.get("automatable"),
                    case.get("blocked_by_issue"),
                ]
            )
        self.simple_table(
            ["Test Case", "Scenario", "Status", "Pri.", "Auto.", "Blocked"],
            rows,
            (28, 24, 20, 14, 16, 20),
        )

        for case in cases:
            if not isinstance(case, dict):
                continue
            title = (
                f"{case.get('test_case_id', '')}  {case.get('title') or ''}  "
                f"({case.get('scenario_id', '')})"
            )
            if case.get("status") == "blocked":
                self.card(
                    title + "  -- BLOCKED",
                    [
                        ("Objective", case.get("objective")),
                        ("Blocked by issue", case.get("blocked_by_issue")),
                        ("Reason", case.get("reason")),
                    ],
                    accent=BLOCKED_COLOR,
                    bg=BLOCKED_BG,
                )
            else:
                self.card(
                    title,
                    [
                        ("Objective", case.get("objective")),
                        ("Preconditions", case.get("preconditions")),
                        ("Steps", _format_steps(case.get("steps"))),
                        ("Overall expected result", case.get("overall_expected_result")),
                        ("Automatable", case.get("automatable")),
                        ("Blocked by issue (traceability only)", case.get("blocked_by_issue")),
                        ("Assumption used", case.get("reason")),
                    ],
                    accent=PRIORITY_COLORS.get(case.get("priority"), ACCENT),
                )

    def _render_generic(self, data) -> None:
        if _is_blank(data):
            self.na_banner("No content generated for this section.")
            return
        if isinstance(data, dict):
            for key, value in data.items():
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
    title = "Detailed Test Cases"
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
        i += 1
    return title, subtitle, sections


def markdown_to_pdf(md_path: str, pdf_path: str) -> None:
    with open(md_path, encoding="utf-8") as f:
        source = f.read()

    title, subtitle, sections = _parse_markdown(source)
    pdf = TestCasePdf()
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
