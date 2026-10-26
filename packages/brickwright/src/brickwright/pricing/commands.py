"""CLI integration for live pricing of exported build records or LDraw files."""

import json
from hashlib import sha256
from pathlib import Path
from typing import Annotated

import typer

from ..config import DEFAULT_RECORDS_DIR, RECORDS_DIR_ENV, Config
from ..record import Record
from . import PickABrickClient, PricingError, bom_from_ldraw


def price(
    record_id: Annotated[
        str | None, typer.Argument(help="finalized build record id")
    ] = None,
    ldraw: Annotated[
        Path | None, typer.Option(help="price an existing .ldr/.mpd file")
    ] = None,
    locale: Annotated[
        str, typer.Option(help="LEGO storefront locale, e.g. en-us or en-gb")
    ] = "en-us",
    out: Annotated[
        Path | None, typer.Option(help="save JSON quote to this path")
    ] = None,
    records_dir: Annotated[Path, typer.Option(envvar=RECORDS_DIR_ENV)] = Path(
        DEFAULT_RECORDS_DIR
    ),
) -> None:
    """Retrieve live LEGO parts prices for a finalized record or --ldraw file.

    Prints JSON. Exit 0: complete and purchasable; 2: partial or unavailable;
    1: lookup/input failure. A record quote is saved to out/price.json.
    """
    if (record_id is None) == (ldraw is None):
        raise typer.BadParameter("provide either a record id or --ldraw")
    try:
        record = None
        source_hash = None
        if record_id is not None:
            record = Record.load(Config(records_dir=records_dir), record_id)
            meta = record.read_meta()
            source_hash = record.source_sha256
            if (
                not meta.finalized
                or meta.exported_source_sha256 != source_hash
                or not record.ldr_path.is_file()
            ):
                raise ValueError(
                    "Finalize the current build before pricing: brickwright external finalize <record_id>"
                )
            ldraw = record.ldr_path
            out = out or record.out_dir / "price.json"
        assert ldraw is not None
        if out is not None and out.resolve() == ldraw.resolve():
            raise ValueError("Quote output must not overwrite the LDraw input")
        text = ldraw.read_text(encoding="utf-8")
        digest = sha256(text.encode()).hexdigest()
        with PickABrickClient(locale) as client:
            quote = client.quote(bom_from_ldraw(text))
        if (record is not None and record.source_sha256 != source_hash) or sha256(
            ldraw.read_text(encoding="utf-8").encode()
        ).hexdigest() != digest:
            raise ValueError("Build changed during pricing; finalize and retry")
        data = quote.model_dump(mode="json")
        data["ldraw_sha256"] = digest
        if record is not None:
            data["record_id"] = record.id
            data["source_sha256"] = source_hash
        rendered = json.dumps(data, indent=2) + "\n"
        if out is not None:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(rendered, encoding="utf-8")
    except (OSError, ValueError, PricingError) as exc:
        typer.echo(f"Pricing failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    typer.echo(rendered, nl=False)
    if not quote.purchasable:
        raise typer.Exit(2)
