"""Export a finalized Brickwright record with a fresh quote and LEGO upload CSV."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import shutil
import sys
import tempfile
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from bricklayer import Color
from brickwright.config import Config
from brickwright.pricing import (
    BuildQuote,
    PickABrickClient,
    PricingError,
    QuoteLine,
    bom_from_ldraw,
)
from brickwright.record import Record

COLORS = {c.ldraw_id: c.name.replace("_", " ").title() for c in Color}
FIELDS = [
    "elementId",
    "ldraw_id",
    "color",
    "color_code",
    "name",
    "quantity",
    "unit_price",
    "line_total",
    "currency",
    "status",
    "max_order_quantity",
]


def money(cents: int | None) -> str:
    return "" if cents is None else f"{cents // 100}.{cents % 100:02d}"


def safe_cell(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_text(header: list[str], rows: list[list[Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows([[safe_cell(value) for value in row] for row in rows])
    return stream.getvalue()


def upload_csv(quote: BuildQuote) -> tuple[str | None, list[QuoteLine]]:
    """Never guess IDs, omit errors silently, clip quantities, or bypass limits."""
    groups: dict[str, list[QuoteLine]] = defaultdict(list)
    omitted = []
    for line in quote.lines:
        if (
            line.status != "available"
            or not line.element_id
            or not re.fullmatch(r"[0-9]+", line.element_id)
        ):
            omitted.append(line)
        else:
            groups[line.element_id].append(line)
    rows = []
    for element_id, lines in sorted(groups.items()):
        quantity = sum(line.quantity for line in lines)
        limit = min(
            [999]
            + [
                line.max_order_quantity
                for line in lines
                if line.max_order_quantity is not None
            ]
        )
        if quantity > limit:
            omitted.extend(lines)
        else:
            rows.append([element_id, quantity])
    if len(rows) > 200:
        raise ValueError(
            "Keep builds within 200 distinct elements for cross-market uploads."
        )
    return (csv_text(["elementId", "quantity"], rows) if rows else None), omitted


def breakdown_rows(lines: list[QuoteLine], currency: str) -> list[list[Any]]:
    return [
        [
            line.element_id or "",
            line.ldraw_id,
            COLORS.get(line.color_code, "Unknown"),
            line.color_code,
            line.name or "",
            line.quantity,
            money(line.unit_price_cents),
            money(line.line_total_cents),
            currency,
            line.status,
            line.max_order_quantity,
        ]
        for line in lines
    ]


def write_bundle(
    out: Path, ldraw: str, quote: BuildQuote, *, record_id: str, source_hash: str
) -> dict[str, Any]:
    upload, omitted = upload_csv(quote)
    full_upload = bool(upload) and not omitted and quote.purchasable
    upload_name = (
        ("pick-a-brick.csv" if full_upload else "pick-a-brick-available.csv")
        if upload
        else None
    )
    out.mkdir(parents=True, exist_ok=False)
    (out / "build.ldr").write_text(ldraw, encoding="utf-8")
    data = quote.model_dump(mode="json")
    data.update(
        record_id=record_id,
        source_sha256=source_hash,
        ldraw_sha256=sha256(ldraw.encode()).hexdigest(),
        upload_complete=full_upload,
        upload_file=upload_name,
        omitted_quantity=sum(line.quantity for line in omitted),
    )
    (out / "price.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    (out / "price-breakdown.csv").write_text(
        csv_text(FIELDS, breakdown_rows(quote.lines, quote.currency)),
        encoding="utf-8",
        newline="",
    )
    if upload_name:
        (out / upload_name).write_text(upload or "", encoding="utf-8", newline="")
    if omitted:
        (out / "missing-pieces.csv").write_text(
            csv_text(
                FIELDS + ["upload_issue"],
                [
                    row
                    + [
                        line.status
                        if line.status != "available"
                        else "invalid_element_id_or_combined_quantity_limit"
                    ]
                    for row, line in zip(
                        breakdown_rows(omitted, quote.currency), omitted, strict=True
                    )
                ],
            ),
            encoding="utf-8",
            newline="",
        )
    total = (
        f"{quote.currency} {money(quote.total_cents)}"
        if quote.complete
        else f"Partial known subtotal: {quote.currency} {money(quote.known_subtotal_cents)}"
    )
    table = [
        "| Piece / color | Element ID | Qty | Unit | Line total | Status |",
        "|---|---|---:|---:|---:|---|",
    ]
    for line in quote.lines:
        name = (line.name or line.ldraw_id).replace("|", "/").replace("\n", " ")
        table.append(
            f"| {name} / {COLORS.get(line.color_code, str(line.color_code))} | {line.element_id or '—'} | {line.quantity} | {money(line.unit_price_cents) or '—'} | {money(line.line_total_cents) or '—'} | {line.status} |"
        )
    upload_note = (
        f"Upload `{upload_name}` at LEGO Pick a Brick → Upload List → View All Pieces."
        if full_upload
        else "Partial order: review `missing-pieces.csv`. The available-pieces CSV, if present, does not contain the entire build. Quantities exceeding the upload limit are omitted, not reduced."
    )
    (out / "BUILD.md").write_text(
        "# Your LEGO build\n\n"
        f"{quote.total_quantity} pieces · {len(quote.lines)} part/color combinations\n\n"
        f"**Parts price: {total}**\n\n"
        f"Market: {quote.locale} · checked {quote.checked_at.isoformat()}\n\n"
        + quote.notice
        + "\n\n"
        + upload_note
        + "\n\n"
        f"[Open LEGO Pick a Brick](https://www.lego.com/{quote.locale}/pick-and-build/pick-a-brick)\n\n"
        + "\n".join(table)
        + "\n\nOpen `build.ldr` in an LDraw-compatible model viewer. This model is not a step-by-step instruction booklet.\n",
        encoding="utf-8",
    )
    return data


def export_record(record_path: Path, out: Path, locale: str) -> dict[str, Any]:
    record_path, out = record_path.resolve(), out.resolve()
    if out.exists():
        raise FileExistsError(f"Choose a new output folder; {out} already exists.")
    if out.is_relative_to(record_path):
        raise ValueError("Save the delivered kit outside the source record.")
    record = Record.load(Config(records_dir=record_path.parent), record_path.name)
    source_hash = record.source_sha256
    if not record.read_meta().finalized:
        raise ValueError("Validate and finalize the current build before exporting.")
    ldraw = record.ldr_path.read_text(encoding="utf-8")
    items = bom_from_ldraw(ldraw)
    with PickABrickClient(locale) as client:
        quote = client.quote(items)
    if (
        record.source_sha256 != source_hash
        or not record.read_meta().finalized
        or record.ldr_path.read_text(encoding="utf-8") != ldraw
    ):
        raise ValueError("Build changed during lookup; finalize and export again.")
    out.parent.mkdir(parents=True, exist_ok=True)
    # Assemble privately, then publish the complete folder so failed exports leave no stale kit.
    with tempfile.TemporaryDirectory(prefix=".lego-build-", dir=out.parent) as temp:
        kit = Path(temp) / "kit"
        data = write_bundle(
            kit, ldraw, quote, record_id=record.id, source_hash=source_hash
        )
        shutil.copy2(record.build_path, kit / "build.py")
        if record.render_path.is_file():
            shutil.copy2(record.render_path, kit / "build.png")
        else:
            from render_preview import render_preview

            render_preview(ldraw, kit / "build.png")
        with ZipFile(kit / "build-kit.zip", "w", ZIP_DEFLATED) as archive:
            for path in sorted(kit.iterdir()):
                if path.suffix != ".zip":
                    archive.write(path, path.name)
        if out.exists():
            raise FileExistsError(f"Output appeared during export: {out}")
        kit.rename(out)
    return {
        "directory": str(out),
        "upload_complete": data["upload_complete"],
        "upload_file": data["upload_file"],
        "parts_total": money(quote.total_cents),
        "known_subtotal": money(quote.known_subtotal_cents),
        "currency": quote.currency,
        "locale": quote.locale,
        "pieces": quote.total_quantity,
        "omitted_quantity": data["omitted_quantity"],
        "files": [p.name for p in sorted(out.iterdir())],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--locale", default="en-us")
    args = parser.parse_args()
    try:
        result = export_record(args.record, args.out, args.locale)
    except (OSError, ValueError, PricingError) as exc:
        print(f"Export failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0 if result["upload_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
