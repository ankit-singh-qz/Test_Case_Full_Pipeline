"""Render a TDD markdown file as a structured PDF.

JSON fences in the markdown are parsed and laid out as labeled fields,
tables, lists, and cards -- not pasted as raw JSON. Same approach as
fdd_pipeline/pdf_export.py, with TDD-specific section renderers.
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
    if isinstance(text, (list, tuple)):
        text = ", ".join(_pdf_text(item) for item in text)
    elif isinstance(text, dict):
        text = "; ".join(f"{_label(k)}: {_pdf_text(v)}" for k, v in text.items())
    else:
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
        "\u2192": "->",
        "\u2190": "<-",
        "\u21d2": "=>",
        "\u2264": "<=",
        "\u2265": ">=",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def _label(key: str) -> str:
    return key.replace("_", " ").strip().title()


def _is_blank(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


class TddPdf(FPDF):
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
        self.cell(120, 5, "Technical Design Document")
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
        self.cell(0, 6, "TECHNICAL DESIGN DOCUMENT")
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

    def decision_box(self, items: list) -> None:
        if not items:
            return
        self.subhead("Decisions Made")
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
        self.set_x(self.l_margin)
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
        if data.get("applicable") is False:
            self.na_banner("Not applicable to this design -- evaluated and excluded by its agent.")
            if isinstance(data.get("decisions_made"), list):
                self.decision_box(data["decisions_made"])
            return

        decisions = data.get("decisions_made")
        payload = {k: v for k, v in data.items() if k not in {"decisions_made", "applicable"}}

        if "technical_artifact_id" in payload or "source_fdd_id" in payload:
            self._render_metadata(payload)
        elif "components" in payload or "data_flow" in payload:
            self._render_architecture(payload)
        elif "stack" in payload:
            self._render_stack(payload)
        elif "columns" in payload or "table_name" in payload:
            self._render_schema(payload)
        elif "endpoints" in payload:
            self._render_apis(payload)
        elif "sequence" in payload:
            self._render_sequence(payload)
        elif "cadence" in payload or "duplicate_prevention" in payload:
            self._render_jobs(payload)
        elif "ttl_seconds" in payload or "invalidation_rule" in payload:
            self._render_caching(payload)
        elif "lock_strategy" in payload or "reconciliation_notes" in payload:
            self._render_concurrency(payload)
        elif "event_schema" in payload or "topic_name" in payload:
            self._render_events(payload)
        elif "mechanisms" in payload:
            self._render_resilience(payload)
        elif "transport_encryption" in payload or "token_scopes" in payload:
            self._render_security(payload)
        elif "log_fields" in payload or "metrics" in payload:
            self._render_observability(payload)
        elif "chosen_strategy" in payload or (
            "steps" in payload and "justification" in payload
        ):
            self._render_deployment(payload)
        elif "config_key" in payload or "fallback_behavior" in payload:
            self._render_kill_switch(payload)
        elif "decisions" in payload:
            self._render_open_decisions(payload)
        else:
            self._render_generic(payload)

        if isinstance(decisions, list):
            self.decision_box(decisions)

    def _render_metadata(self, data: dict) -> None:
        self.two_col_kv(
            [
                ("Technical Artifact ID", data.get("technical_artifact_id")),
                ("Version", data.get("version")),
                ("Source FDD ID", data.get("source_fdd_id")),
                ("Source FDD Tier", data.get("source_fdd_tier")),
                ("Status", data.get("status")),
            ]
        )
        leftover = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "technical_artifact_id",
                "version",
                "source_fdd_id",
                "source_fdd_tier",
                "status",
            }
        }
        self._render_generic(leftover)

    def _render_architecture(self, data: dict) -> None:
        components = data.get("components") or []
        self.subhead(f"Components ({len(components)})")
        for component in components:
            if not isinstance(component, dict):
                self.bullets([component])
                continue
            self.card(
                component.get("name") or "Component",
                [("Justified by", component.get("justified_by"))],
            )
        flows = data.get("data_flow") or []
        self.subhead("Data Flow")
        if flows and all(isinstance(item, str) for item in flows):
            for flow in flows:
                self.ensure(8)
                self.set_x(self.l_margin)
                self.set_font("Helvetica", "", 10)
                self.set_text_color(*INK)
                self.multi_cell(self.usable, 6, _pdf_text(flow.replace("\u2192", "  ->  ")))
            self.ln(2)
        else:
            self.bullets(flows)
        leftover = {
            k: v for k, v in data.items() if k not in {"components", "data_flow"}
        }
        self._render_generic(leftover)

    def _render_stack(self, data: dict) -> None:
        stack = data.get("stack") or []
        self.subhead(f"Stack ({len(stack)})")
        for item in stack:
            if not isinstance(item, dict):
                self.bullets([item])
                continue
            layer = item.get("layer") or "Layer"
            choice = item.get("choice") or ""
            title = f"{layer}  |  {choice}" if choice else str(layer)
            self.card(title, [("Justification", item.get("justification"))])
        leftover = {k: v for k, v in data.items() if k != "stack"}
        self._render_generic(leftover)

    def _render_schema(self, data: dict) -> None:
        if data.get("table_name"):
            self.kv("Table", data.get("table_name"))
        columns = data.get("columns") or []
        self.subhead(f"Columns ({len(columns)})")
        rows = []
        for col in columns:
            if not isinstance(col, dict):
                rows.append([str(col), "", "", ""])
                continue
            constraints = col.get("constraints") or []
            if isinstance(constraints, list):
                constraints_txt = ", ".join(str(c) for c in constraints)
            else:
                constraints_txt = str(constraints)
            rows.append(
                [
                    col.get("name") or "",
                    col.get("sql_type") or "",
                    constraints_txt,
                    col.get("source_fdd_field") or "",
                ]
            )
        self.simple_table(
            ["Column", "Type", "Constraints", "FDD field"],
            rows,
            (24, 18, 36, 22),
        )
        indices = data.get("indices") or []
        if indices:
            self.subhead(f"Indices ({len(indices)})")
            for index in indices:
                if not isinstance(index, dict):
                    self.bullets([index])
                    continue
                self.card(
                    index.get("definition") or "Index",
                    [("Justification", index.get("justification"))],
                )
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"table_name", "columns", "indices"}
        }
        self._render_generic(leftover)

    def _render_apis(self, data: dict) -> None:
        endpoints = data.get("endpoints") or []
        self.subhead(f"Endpoints ({len(endpoints)})")
        for endpoint in endpoints:
            if not isinstance(endpoint, dict):
                self.bullets([endpoint])
                continue
            success = endpoint.get("success_response") or {}
            success_fields = success.get("fields") if isinstance(success, dict) else None
            success_status = success.get("status") if isinstance(success, dict) else None
            self.card(
                endpoint.get("route") or "Endpoint",
                [
                    ("Description", endpoint.get("description")),
                    ("Request fields", endpoint.get("request_fields")),
                    ("Success status", success_status),
                    ("Success fields", success_fields),
                ],
            )
            errors = endpoint.get("error_responses") or []
            if errors and isinstance(errors[0], dict):
                rows = [
                    [
                        item.get("error_code") or "",
                        str(item.get("http_status") or ""),
                        item.get("message") or "",
                    ]
                    for item in errors
                ]
                self.simple_table(
                    ["Error code", "HTTP", "Message"],
                    rows,
                    (28, 10, 62),
                )
            leftover_keys = {
                k: v
                for k, v in endpoint.items()
                if k
                not in {
                    "route",
                    "description",
                    "request_fields",
                    "success_response",
                    "error_responses",
                }
            }
            self._render_generic(leftover_keys)
        leftover = {k: v for k, v in data.items() if k != "endpoints"}
        self._render_generic(leftover)

    def _render_sequence(self, data: dict) -> None:
        steps = data.get("sequence") or []
        self.subhead("Sequence")
        if steps and isinstance(steps[0], dict):
            rows = [
                [
                    str(item.get("step") or ""),
                    item.get("from_component") or "",
                    item.get("to_component") or "",
                    item.get("fdd_req_id") or "",
                ]
                for item in steps
            ]
            self.simple_table(
                ["Step", "From", "To", "FDD req"],
                rows,
                (10, 34, 34, 22),
            )
        else:
            self.numbered(steps)
        leftover = {k: v for k, v in data.items() if k != "sequence"}
        self._render_generic(leftover)

    def _render_jobs(self, data: dict) -> None:
        self.kv("Cadence", data.get("cadence"))
        self.kv("Duplicate prevention", data.get("duplicate_prevention"))
        self.kv("Retry threshold", data.get("retry_threshold"))
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"cadence", "duplicate_prevention", "retry_threshold"}
        }
        self._render_generic(leftover)

    def _render_caching(self, data: dict) -> None:
        self.kv("Strategy", data.get("strategy"))
        self.kv("TTL seconds", data.get("ttl_seconds"))
        self.kv("Invalidation rule", data.get("invalidation_rule"))
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"strategy", "ttl_seconds", "invalidation_rule"}
        }
        self._render_generic(leftover)

    def _render_concurrency(self, data: dict) -> None:
        self.kv("Lock strategy", data.get("lock_strategy"))
        self.kv("Reconciliation notes", data.get("reconciliation_notes"))
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"lock_strategy", "reconciliation_notes"}
        }
        self._render_generic(leftover)

    def _render_events(self, data: dict) -> None:
        self.kv("Topic", data.get("topic_name"))
        schema = data.get("event_schema") or {}
        if isinstance(schema, dict) and schema:
            self.subhead("Event Schema")
            rows = [[key, str(value)] for key, value in schema.items()]
            self.simple_table(["Field", "Type"], rows, (50, 50))
        leftover = {
            k: v for k, v in data.items() if k not in {"topic_name", "event_schema"}
        }
        self._render_generic(leftover)

    def _render_resilience(self, data: dict) -> None:
        mechanisms = data.get("mechanisms") or []
        self.subhead(f"Mechanisms ({len(mechanisms)})")
        for item in mechanisms:
            if not isinstance(item, dict):
                self.bullets([item])
                continue
            params = item.get("parameters") or {}
            param_text = (
                "\n".join(f"{_label(k)}: {v}" for k, v in params.items())
                if isinstance(params, dict)
                else params
            )
            self.card(
                item.get("mechanism") or "Mechanism",
                [
                    ("FDD scenario", item.get("fdd_scenario")),
                    ("Parameters", param_text),
                ],
            )
        leftover = {k: v for k, v in data.items() if k != "mechanisms"}
        self._render_generic(leftover)

    def _render_security(self, data: dict) -> None:
        self.kv("Transport encryption", data.get("transport_encryption"))
        self.kv("At-rest encryption", data.get("at_rest_encryption"))
        auth = data.get("authn_authz")
        if isinstance(auth, dict):
            self.subhead("Authentication & Authorization")
            for key, value in auth.items():
                self.kv(_label(key), value)
        elif auth:
            self.kv("Authn / Authz", auth)
        if "token_scopes" in data:
            self.subhead("Token Scopes")
            self.bullets(data.get("token_scopes") or [])
        if "masking_rules" in data:
            self.subhead("Masking Rules")
            self.bullets(data.get("masking_rules") or [])
        leftover = {
            k: v
            for k, v in data.items()
            if k
            not in {
                "transport_encryption",
                "at_rest_encryption",
                "authn_authz",
                "token_scopes",
                "masking_rules",
            }
        }
        self._render_generic(leftover)

    def _render_observability(self, data: dict) -> None:
        if "log_fields" in data:
            self.subhead("Log Fields")
            self.bullets(data.get("log_fields") or [])
        metrics = data.get("metrics") or []
        self.subhead(f"Metrics ({len(metrics)})")
        if metrics and isinstance(metrics[0], dict):
            rows = [
                [item.get("name") or "", item.get("tracks") or ""] for item in metrics
            ]
            self.simple_table(["Metric", "Tracks"], rows, (38, 62))
        else:
            self.bullets(metrics)
        leftover = {
            k: v for k, v in data.items() if k not in {"log_fields", "metrics"}
        }
        self._render_generic(leftover)

    def _render_deployment(self, data: dict) -> None:
        self.kv("Chosen strategy", data.get("chosen_strategy"))
        if data.get("justification"):
            self.kv("Justification", data.get("justification"))
        steps = data.get("steps") or []
        self.subhead(f"Rollout Steps ({len(steps)})")
        for step in steps:
            if not isinstance(step, dict):
                self.bullets([step])
                continue
            actions = step.get("actions") or []
            if isinstance(actions, list):
                actions_txt = "\n".join(f"- {action}" for action in actions)
            else:
                actions_txt = str(actions)
            title = step.get("phase") or "Phase"
            if step.get("duration"):
                title = f"{title}  |  {step.get('duration')}"
            self.card(title, [("Actions", actions_txt)])
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"chosen_strategy", "justification", "steps"}
        }
        self._render_generic(leftover)

    def _render_kill_switch(self, data: dict) -> None:
        self.kv("Config key", data.get("config_key"))
        self.kv("Fallback behavior", data.get("fallback_behavior"))
        leftover = {
            k: v
            for k, v in data.items()
            if k not in {"config_key", "fallback_behavior"}
        }
        self._render_generic(leftover)

    def _render_open_decisions(self, data: dict) -> None:
        decisions = data.get("decisions") or []
        self.subhead(f"Open Decisions ({len(decisions)})")
        for item in decisions:
            if not isinstance(item, dict):
                self.bullets([item])
                continue
            source = item.get("source_section")
            title = item.get("decision") or "Decision"
            if source:
                title = f"{title}  [section {source}]"
            self.card(
                title,
                [
                    ("Why not derivable", item.get("why_not_derivable")),
                    ("Chosen", item.get("chosen")),
                    ("Rationale", item.get("rationale")),
                ],
                accent=(168, 84, 36),
            )
        leftover = {k: v for k, v in data.items() if k != "decisions"}
        self._render_generic(leftover)

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
                            title = (
                                item.get("name")
                                or item.get("title")
                                or item.get("route")
                                or item.get("mechanism")
                                or item.get("decision")
                                or _label(key)
                            )
                            fields = [
                                (_label(k), v)
                                for k, v in item.items()
                                if k not in {"name", "title", "route", "mechanism", "decision"}
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
    title = "Technical Design Document"
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
    pdf = TddPdf()
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
