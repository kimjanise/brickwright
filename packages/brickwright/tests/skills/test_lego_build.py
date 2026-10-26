import csv
import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

from brickwright.pricing import BuildQuote, QuoteLine

SCRIPT = (
    Path(__file__).resolve().parents[4] / "skills/lego-build/scripts/export_bundle.py"
)
spec = importlib.util.spec_from_file_location("lego_export", SCRIPT)
assert spec and spec.loader
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


def line(**changes):
    data = {
        "ldraw_id": "3001",
        "color_code": 4,
        "quantity": 2,
        "status": "available",
        "element_id": "300121",
        "name": "BRICK 2X4",
        "unit_price_cents": 21,
        "line_total_cents": 42,
        "max_order_quantity": 999,
    }
    return QuoteLine.model_validate(data | changes)


def quote(lines):
    complete = all(x.line_total_cents is not None for x in lines)
    total = sum(x.line_total_cents or 0 for x in lines)
    return BuildQuote(
        locale="en-us",
        currency="USD",
        checked_at=datetime.now(UTC),
        complete=complete,
        purchasable=all(x.status == "available" for x in lines),
        total_quantity=sum(x.quantity for x in lines),
        priced_quantity=sum(
            x.quantity for x in lines if x.line_total_cents is not None
        ),
        known_subtotal_cents=total,
        total_cents=total if complete else None,
        lines=lines,
    )


def test_exact_official_csv_header_and_quantities():
    content, omitted = export.upload_csv(quote([line()]))
    assert content == "elementId,quantity\r\n300121,2\r\n"
    assert omitted == []


def test_unavailable_and_unknown_ids_never_enter_upload():
    content, omitted = export.upload_csv(
        quote(
            [
                line(),
                line(
                    ldraw_id="3003",
                    status="not_found",
                    element_id=None,
                    unit_price_cents=None,
                    line_total_cents=None,
                ),
                line(ldraw_id="3004", status="out_of_stock", element_id="300421"),
            ]
        )
    )
    assert content.count("\r\n") == 2
    assert len(omitted) == 2


def test_duplicate_elements_aggregate_and_respect_limit():
    content, omitted = export.upload_csv(
        quote([line(quantity=500), line(quantity=500)])
    )
    assert content is None
    assert len(omitted) == 2
    content, omitted = export.upload_csv(quote([line(), line()]))
    assert "300121,4\r\n" in content


def test_partial_bundle_is_labeled_and_breakdown_preserves_unknown(tmp_path):
    q = quote(
        [
            line(),
            line(
                ldraw_id="3003",
                status="not_found",
                element_id=None,
                unit_price_cents=None,
                line_total_cents=None,
            ),
        ]
    )
    out = tmp_path / "kit"
    export.write_bundle(out, "0 Test\n", q, record_id="test", source_hash="abc")
    assert not (out / "pick-a-brick.csv").exists()
    assert (out / "pick-a-brick-available.csv").exists()
    rows = list(csv.DictReader((out / "price-breakdown.csv").open()))
    assert rows[1]["unit_price"] == ""
    assert rows[1]["status"] == "not_found"
    assert "Partial" in (out / "BUILD.md").read_text()
    assert (out / "missing-pieces.csv").exists()


def test_existing_output_never_overwritten(tmp_path):
    with pytest.raises(FileExistsError):
        export.write_bundle(
            tmp_path, "0 Test\n", quote([line()]), record_id="test", source_hash="abc"
        )


def test_csv_formula_in_names_is_inert(tmp_path):
    out = tmp_path / "kit"
    export.write_bundle(
        out,
        "0 Test\n",
        quote([line(name='=HYPERLINK("bad")')]),
        record_id="test",
        source_hash="abc",
    )
    rows = list(csv.DictReader((out / "price-breakdown.csv").open()))
    assert rows[0]["name"].startswith("'=")


def test_unfinalized_build_cannot_be_priced_or_exported(record, tmp_path):
    with pytest.raises(ValueError, match="finalize"):
        export.export_record(record.path, tmp_path / "kit", "en-us")
    assert not (tmp_path / "kit").exists()


def test_preview_renders_real_parts_without_clipping(tmp_path):
    import numpy as np
    from PIL import Image

    preview_spec = importlib.util.spec_from_file_location(
        "lego_preview", SCRIPT.with_name("render_preview.py")
    )
    assert preview_spec and preview_spec.loader
    preview = importlib.util.module_from_spec(preview_spec)
    preview_spec.loader.exec_module(preview)
    path = tmp_path / "build.png"
    preview.render_preview("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat", path)
    image = np.array(Image.open(path))
    background = image[0, 0]
    assert np.any(image != background)
    assert np.all(image[0] == background)
    assert np.all(image[-1] == background)
    assert np.all(image[:, 0] == background)
    assert np.all(image[:, -1] == background)


def test_build_changed_during_quote_does_not_publish(record, tmp_path, monkeypatch):
    from brickwright.record import Status

    record.ldr_path.write_text("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat")
    record.update_meta(
        finalized=True,
        status=Status.VALID,
        validated_source_sha256=record.source_sha256,
        exported_source_sha256=record.source_sha256,
    )

    class ChangingClient:
        def __init__(self, locale):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def quote(self, items):
            record.build_path.write_text(
                record.build_path.read_text() + "\n# changed\n"
            )
            return quote([line()])

    monkeypatch.setattr(export, "PickABrickClient", ChangingClient)
    with pytest.raises(ValueError, match="changed"):
        export.export_record(record.path, tmp_path / "kit", "en-us")
    assert not (tmp_path / "kit").exists()
