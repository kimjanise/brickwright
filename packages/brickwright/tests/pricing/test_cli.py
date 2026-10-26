import json

import httpx
import pytest
from typer.testing import CliRunner

from brickwright.cli import app
from brickwright.pricing import PickABrickClient
from brickwright.record import Status


@pytest.fixture
def mock_lego(monkeypatch):
    def make(locale="en-us"):
        return PickABrickClient(
            locale,
            http=httpx.Client(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(
                        200,
                        json={
                            "data": {
                                "searchElements": {
                                    "results": [
                                        {
                                            "id": "300121",
                                            "designId": "3001",
                                            "name": "BRICK 2X4",
                                            "availability": "AVAILABLE",
                                            "deliveryChannel": "pab",
                                            "facets": {
                                                "color": {
                                                    "key": "21",
                                                    "name": "Bright Red",
                                                }
                                            },
                                            "price": {
                                                "centAmount": 21,
                                                "currencyCode": "USD",
                                            },
                                        }
                                    ],
                                    "total": 1,
                                    "count": 1,
                                }
                            }
                        },
                    )
                )
            ),
        )

    monkeypatch.setattr("brickwright.pricing.commands.PickABrickClient", make)


def test_price_ldraw(tmp_path, mock_lego):
    path = tmp_path / "build.ldr"
    path.write_text("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat")
    out = tmp_path / "price.json"
    result = CliRunner().invoke(app, ["price", "--ldraw", str(path), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["total_cents"] == 21
    assert json.loads(out.read_text())["total_cents"] == 21


def test_price_record_requires_current_export(record, mock_lego):
    result = CliRunner().invoke(
        app, ["price", record.id, "--records-dir", str(record.path.parent)]
    )
    assert result.exit_code != 0
    assert "finaliz" in result.output.lower()


def test_price_failure_does_not_write_a_fake_quote(tmp_path, mock_lego):
    path = tmp_path / "build.ldr"
    path.write_text("1 4 0 0 0 1 0 0 0 1 0 0 0 1 missing.dat")
    out = tmp_path / "price.json"
    result = CliRunner().invoke(app, ["price", "--ldraw", str(path), "--out", str(out)])
    assert result.exit_code != 0
    assert not out.exists()


def test_record_quote_is_saved_and_cleared_with_exports(record, mock_lego):
    record.out_dir.mkdir(parents=True, exist_ok=True)
    record.ldr_path.write_text("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat")
    record.update_meta(
        finalized=True,
        status=Status.VALID,
        validated_source_sha256=record.source_sha256,
        exported_source_sha256=record.source_sha256,
    )
    result = CliRunner().invoke(
        app, ["price", record.id, "--records-dir", str(record.path.parent)]
    )
    assert result.exit_code == 0, result.output
    saved = record.out_dir / "price.json"
    data = json.loads(saved.read_text())
    assert data["source_sha256"] == record.source_sha256
    assert data["record_id"] == record.id
    record.clear_exports()
    assert not saved.exists()


def test_partial_quote_is_saved_with_nonzero_exit(tmp_path, mock_lego):
    path = tmp_path / "build.ldr"
    path.write_text("1 1 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat")
    result = CliRunner().invoke(app, ["price", "--ldraw", str(path)])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["total_cents"] is None
