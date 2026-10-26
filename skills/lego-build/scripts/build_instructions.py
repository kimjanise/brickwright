"""Illustrate explicitly authored LDraw steps; never infer assembly from file order."""

from __future__ import annotations

import json
import warnings
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from bricklayer import Element, LegoBuild
from bricklayer.io import from_ldraw, to_ldraw
from bricklayer.io.reader import LDrawImportWarning
from render_preview import render_preview
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph


def assembly_steps(ldraw: str):
    with warnings.catch_warnings():
        warnings.simplefilter("error", LDrawImportWarning)
        try:
            model = from_ldraw(ldraw)
        except LDrawImportWarning as exc:
            raise ValueError(f"Cannot illustrate incomplete geometry: {exc}") from exc
    if not 0 < model.brick_count <= 2000:
        raise ValueError("Instructions support 1-2,000 pieces.")
    if any(not isinstance(p.content, Element) for p in model.placements):
        raise ValueError(
            "Instructions require flat part placements with authored steps."
        )
    steps = [step for step in model.steps if step]
    if model.brick_count > 1 and not model.step_markers:
        raise ValueError("Author assembly steps with add_step() before exporting.")
    for step in steps:
        if (
            len(step) > 12
            or len({(p.content.ldraw_id, p.content.color.ldraw_id) for p in step}) > 6
        ):
            raise ValueError(
                "Split each step into at most 12 pieces and 6 part/color types."
            )
    return model, steps


def text_block(
    pdf: Canvas, text: str, x: float, top: float, width: float, size: int = 11
) -> None:
    paragraph = Paragraph(
        escape(text),
        ParagraphStyle(
            "body",
            fontName="Helvetica",
            fontSize=size,
            leading=size * 1.4,
            textColor=colors.HexColor("#35464d"),
        ),
    )
    _, height = paragraph.wrap(width, 800)
    paragraph.drawOn(pdf, x, top - height)


def write_instructions(
    ldraw: str, out: Path, notes: dict[str, Any] | None = None
) -> dict:
    model, steps = assembly_steps(ldraw)
    notes = notes or {}
    authored = notes.get("steps", [{} for _ in steps])
    if not isinstance(authored, list) or len(authored) != len(steps):
        raise ValueError("Instruction notes must match the nonempty LDraw steps.")
    title = notes.get("title", "Your custom LEGO build")
    preparation = notes.get(
        "preparation",
        "Build on a flat surface. Compare both views before attaching each group of pieces.",
    )
    for value, limit in [(title, 70), (preparation, 420)]:
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(
                f"Instruction text must be a string of at most {limit} characters."
            )
    for note in authored:
        if not isinstance(note, dict) or any(
            not isinstance(note.get(key, ""), str) or len(note.get(key, "")) > limit
            for key, limit in [("title", 70), ("note", 320)]
        ):
            raise ValueError(
                "Step titles/notes must be short strings (70/320 characters)."
            )
    out.mkdir(parents=True, exist_ok=True)
    images = out / "steps"
    images.mkdir(exist_ok=False)
    preview = out / "build.png"
    if not preview.exists():
        render_preview(ldraw, preview)
    pdf = Canvas(str(out / "instructions.pdf"), pagesize=(595, 842))
    pdf.setTitle(title + " - assembly instructions")
    pdf.setAuthor("LEGO Build / Brickwright")

    def page(label: str, number: int):
        pdf.setFillColor(colors.HexColor("#fafaf7"))
        pdf.rect(0, 0, 595, 842, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#17634b"))
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(36, 803, "LEGO BUILD  /  ASSEMBLY GUIDE")
        pdf.setFillColor(colors.HexColor("#172d35"))
        pdf.setFont("Helvetica-Bold", 21)
        pdf.drawString(36, 768, label)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(
            36,
            24,
            "Independent fan-created guide. Not an official LEGO instruction booklet.",
        )
        pdf.drawRightString(559, 24, f"{number} / {len(steps) + 1}")

    page("Build something of your own", 1)
    text_block(pdf, title, 36, 739, 523, 17)
    text_block(
        pdf, f"{model.brick_count} pieces  |  {len(steps)} assembly steps", 36, 680, 523
    )
    pdf.drawImage(str(preview), 87, 240, width=420, height=420)
    text_block(pdf, preparation, 36, 223, 523)
    text_block(
        pdf,
        "How to read: new pieces retain their actual colors; pieces already placed are gray. Each step includes two views and its parts list. The cover shows the complete model in color.",
        36,
        145,
        523,
    )
    text_block(
        pdf,
        "The finished geometry is validated. Assembly order is agent-authored and has not been physically tested; hold loose pieces or subassemblies until secured.",
        36,
        78,
        523,
        9,
    )
    pdf.showPage()
    manifest: dict[str, Any] = {
        "title": title,
        "preparation": preparation,
        "ldraw_sha256": sha256(ldraw.encode()).hexdigest(),
        "pieces": model.brick_count,
        "steps": [],
    }
    count = 0
    for index, (group, note) in enumerate(zip(steps, authored, strict=True), 1):
        previous, count = count, count + len(group)
        partial = to_ldraw(LegoBuild(model.placements[:count]))
        front, back = images / f"{index:03}-front.png", images / f"{index:03}-back.png"
        render_preview(partial, front, new_from=previous)
        render_preview(partial, back, new_from=previous, camera=(1.0, -0.7, 1.3))
        title = note.get("title", "Add the highlighted pieces")
        page(f"Step {index:02} / {len(steps):02}", index + 1)
        text_block(pdf, title, 36, 740, 523, 16)
        text_block(
            pdf,
            note.get(
                "note", "Match the placement and orientation shown in both views."
            ),
            36,
            690,
            523,
        )
        pdf.drawImage(str(front), 32, 365, width=262, height=262)
        pdf.drawImage(str(back), 301, 365, width=262, height=262)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(36, 349, "Front view")
        pdf.drawString(306, 349, "Opposite view")
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(
            36,
            314,
            f"Add {len(group)} piece(s)  /  {count} of {model.brick_count} placed",
        )
        quantities = Counter(
            (
                p.content.ldraw_id,
                p.content.color.name.replace("_", " ").title(),
                p.content.color.rgb,
                p.content.spec.name,
            )
            for p in group
        )
        parts = []
        for row, ((part, color, rgb, name), quantity) in enumerate(quantities.items()):
            y = 282 - row * 33
            pdf.setFillColor(colors.HexColor("#" + rgb))
            pdf.setStrokeColor(colors.HexColor("#718088"))
            pdf.rect(38, y - 5, 13, 13, fill=1, stroke=1)
            text_block(
                pdf, f"{quantity} x  {name[:42]} ({part})  /  {color}", 64, y + 10, 485
            )
            parts.append(
                {"part_id": part, "name": name, "color": color, "quantity": quantity}
            )
        text_block(pdf, "Colored = add now     Gray = already built", 36, 65, 523, 10)
        manifest["steps"].append(
            {
                "number": index,
                "title": title,
                "note": note.get("note", ""),
                "added_quantity": len(group),
                "cumulative_quantity": count,
                "parts": parts,
            }
        )
        pdf.showPage()
    pdf.save()
    (out / "instructions.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
