"""Optional local pricing API: install brickwright[api], then run with uvicorn."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import (
    MAX_LINES,
    BomItem,
    BuildQuote,
    CatalogElement,
    PickABrickClient,
    PricingError,
    bom_from_ldraw,
)

app = FastAPI(title="BrickWright Pick a Brick pricing", version="0.1.0")


@app.exception_handler(PricingError)
def upstream_error(request: Request, exc: PricingError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.exception_handler(ValueError)
def input_error(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


def get_client(locale: str = "en-us") -> Iterator[PickABrickClient]:
    with PickABrickClient(locale) as client:
        yield client


Client = Annotated[PickABrickClient, Depends(get_client)]


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BomItem] = Field(min_length=1, max_length=MAX_LINES)


class LDrawRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ldraw: str = Field(min_length=1, max_length=1_000_000)


class SearchResponse(BaseModel):
    locale: str
    currency: str
    elements: list[CatalogElement]


@app.get("/api/pick-a-brick/search")
def search(
    client: Client, query: Annotated[str, Query(min_length=1, max_length=64)]
) -> SearchResponse:
    """Find LEGO elements by design/element ID or name, in the selected locale."""
    return SearchResponse(
        locale=client.locale, currency=client.currency, elements=client.search(query)
    )


@app.post("/api/pick-a-brick/quote")
def quote(body: QuoteRequest, client: Client) -> BuildQuote:
    """Price a bill of materials using LDraw IDs and LDraw color codes."""
    return client.quote(body.items)


@app.post("/api/pick-a-brick/quote/ldraw")
def quote_ldraw(body: LDrawRequest, client: Client) -> BuildQuote:
    """Price generated LDraw/MPD text; incomplete imports are rejected."""
    return client.quote(bom_from_ldraw(body.ldraw))
