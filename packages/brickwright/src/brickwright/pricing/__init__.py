"""Live, exact part/color pricing from LEGO Pick a Brick.

The storefront GraphQL endpoint is undocumented and can change. Fail closed on
network/schema/currency errors; never replace missing pieces with estimates.
"""

from __future__ import annotations

import warnings
from collections import Counter
from datetime import UTC, datetime
from typing import Literal, Self
from urllib.parse import urlencode

import httpx
from bricklayer import Color, LegoBuild
from bricklayer.io import LDrawImportWarning, from_ldraw
from bricklayer.ldraw.colors import LDrawColor, color_definition, parse_color_definition
from pydantic import BaseModel, ConfigDict, Field, ValidationError

ENDPOINT = "https://www.lego.com/api/graphql/PickABrickQuery"
MARKETS = {
    "en-us": "USD",
    "en-gb": "GBP",
    "en-ca": "CAD",
    "en-au": "AUD",
    "de-de": "EUR",
    "fr-fr": "EUR",
    "nl-nl": "EUR",
}
# Verified against LEGO's storefront query and a live response on 2026-10-25.
QUERY = """query PickABrickQuery($input: ElementQueryInput!) {
  searchElements(input: $input) {
    results {
      id designId name maxOrderQuantity deliveryChannel availability
      facets { color { name key } }
      price { centAmount currencyCode }
    }
    total count
  }
}"""
_COLOR_MAP = {color.ldraw_id: color for color in Color}
MAX_LINES = 200
MAX_QUANTITY = 100_000


class PricingError(RuntimeError):
    """LEGO could not supply a trustworthy quote. Safe to show to a caller."""


class BomItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    ldraw_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    color_code: int = Field(ge=0, strict=True)
    quantity: int = Field(gt=0, le=MAX_QUANTITY, strict=True)


class _Price(BaseModel):
    centAmount: int = Field(ge=0, strict=True)
    currencyCode: str = Field(pattern=r"^[A-Z]{3}$")


class _Color(BaseModel):
    name: str
    key: str


class _Facets(BaseModel):
    color: _Color


class CatalogElement(BaseModel):
    id: str = Field(pattern=r"^[0-9]+$")
    designId: str
    name: str
    maxOrderQuantity: int | None = Field(default=None, ge=0, strict=True)
    deliveryChannel: str | None
    availability: str
    facets: _Facets
    price: _Price | None


class _SearchResult(BaseModel):
    results: list[CatalogElement]
    total: int = Field(ge=0, strict=True)
    count: int = Field(ge=0, strict=True)


class QuoteLine(BomItem):
    status: Literal[
        "available",
        "out_of_stock",
        "quantity_limit",
        "not_found",
        "unmapped_color",
        "price_unavailable",
    ]
    element_id: str | None = None
    lego_color_id: int | None = None
    name: str | None = None
    unit_price_cents: int | None = None
    line_total_cents: int | None = None
    max_order_quantity: int | None = None
    delivery_channel: str | None = None
    url: str | None = None


class BuildQuote(BaseModel):
    source: str = "LEGO Pick a Brick"
    locale: str
    currency: str
    checked_at: datetime
    complete: bool
    purchasable: bool
    total_quantity: int
    priced_quantity: int
    known_subtotal_cents: int
    total_cents: int | None
    lines: list[QuoteLine]
    notice: str = (
        "Current listed parts prices only. Shipping, service fees and any additional "
        "checkout tax are not included. Availability and prices may change at checkout. "
        "A null total means some parts could not be priced; known_subtotal_cents is partial."
    )


def normalize_locale(locale: str) -> str:
    locale = locale.lower()
    if locale not in MARKETS:
        raise ValueError(f"Unsupported locale {locale!r}; choose {', '.join(MARKETS)}")
    return locale


def bom_from_build(build: LegoBuild) -> list[BomItem]:
    """Count every nested placement; reject custom colors that resemble a known ID."""
    items = []
    for element, quantity in build.list_elements().items():
        color = element.color
        known = _COLOR_MAP.get(color.ldraw_id)
        if known is not None and isinstance(color, LDrawColor):
            # Compare with BrickLayer's own serialized palette, including alpha.
            definition = color_definition(known)
            assert definition is not None
            expected = parse_color_definition(definition)
            if (color.finish, color.alpha) != (expected.finish, expected.alpha):
                raise ValueError(
                    f"Custom color {color.ldraw_id} is not the LEGO catalog color"
                )
        if known is not None and color.rgb.upper() != known.rgb:
            raise ValueError(
                f"Custom color {color.ldraw_id} is not the LEGO catalog color"
            )
        items.append(
            BomItem(
                ldraw_id=element.ldraw_id, color_code=color.ldraw_id, quantity=quantity
            )
        )
    return items


def bom_from_ldraw(text: str) -> list[BomItem]:
    """Read generated LDraw/MPD without executing build.py or ignoring skipped parts."""
    if len(text) > 1_000_000:
        raise ValueError("LDraw input exceeds 1 MB")
    if any(
        line.split(maxsplit=1)[0] in {"2", "3", "4", "5"}
        for line in text.splitlines()
        if line.strip()
    ):
        raise ValueError("Raw LDraw geometry cannot be mapped to purchasable parts")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", LDrawImportWarning)
        build = from_ldraw(text)
    if any(issubclass(w.category, LDrawImportWarning) for w in caught):
        raise ValueError(
            "LDraw import is incomplete; resolve missing parts, colors or geometry before pricing"
        )
    return bom_from_build(build)


class PickABrickClient:
    """One quote session. Search results are reused within a quote, never across quotes.

    No credentials or LEGO account are needed. The optional http client makes the
    transport injectable for tests. This object owns and closes that client.
    """

    def __init__(self, locale: str = "en-us", *, http: httpx.Client | None = None):
        self.locale = normalize_locale(locale)
        self.currency = MARKETS[self.locale]
        self.http = http if http is not None else httpx.Client(timeout=15.0)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.http.close()

    def search(self, query: str) -> list[CatalogElement]:
        if not query.strip() or len(query) > 64:
            raise ValueError("Search query must contain 1–64 characters")
        lang, country = self.locale.split("-")
        headers = {
            "Origin": "https://www.lego.com",
            "x-locale": f"{lang}-{country.upper()}",
            "Referer": f"https://www.lego.com/{self.locale}/pick-and-build/pick-a-brick",
            "User-Agent": "Brickwright/0.1 (Pick a Brick pricing)",
        }
        found: dict[str, CatalogElement] = {}
        for page in range(1, 21):
            try:
                response = self.http.post(
                    ENDPOINT,
                    headers=headers,
                    json={
                        "operationName": "PickABrickQuery",
                        "query": QUERY,
                        "variables": {
                            "input": {
                                "query": query,
                                "page": page,
                                "perPage": 50,
                                "availability": ["AVAILABLE", "OUT_OF_STOCK"],
                            }
                        },
                    },
                )
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict) or payload.get("errors"):
                    raise PricingError(
                        "LEGO rejected its storefront query; the upstream API may have changed"
                    )
                result = _SearchResult.model_validate(payload["data"]["searchElements"])
            except httpx.HTTPStatusError as exc:
                raise PricingError(
                    f"LEGO returned HTTP {exc.response.status_code}; try again later"
                ) from exc
            except httpx.RequestError as exc:
                raise PricingError(
                    "Could not reach LEGO Pick a Brick; check your connection and try again"
                ) from exc
            except (ValueError, KeyError, TypeError, ValidationError) as exc:
                raise PricingError(
                    "LEGO returned an invalid response; the upstream API may have changed"
                ) from exc
            if any(
                e.price and e.price.currencyCode != self.currency
                for e in result.results
            ):
                raise PricingError(
                    f"LEGO returned a currency other than {self.currency} for {self.locale}"
                )
            previous = len(found)
            found.update((e.id, e) for e in result.results)
            if len(found) >= result.total:
                return list(found.values())
            if len(found) == previous:
                raise PricingError(
                    "LEGO pagination stopped before all matching elements were returned"
                )
        raise PricingError("LEGO search exceeded 20 pages; use a more specific part ID")

    def quote(self, items: list[BomItem]) -> BuildQuote:
        if not items:
            raise ValueError("Cannot price an empty build")
        if len(items) > MAX_LINES:
            raise ValueError(
                f"At most {MAX_LINES} bill-of-materials lines can be priced at once"
            )
        counts: Counter[tuple[str, int]] = Counter()
        for item in items:
            counts[item.ldraw_id, item.color_code] += item.quantity
        if sum(counts.values()) > MAX_QUANTITY:
            raise ValueError(f"Build exceeds {MAX_QUANTITY} pieces")
        checked_at = datetime.now(UTC)
        catalog: dict[str, list[CatalogElement]] = {}
        lines = []
        for (part, code), quantity in counts.items():
            item = BomItem(ldraw_id=part, color_code=code, quantity=quantity)
            known = _COLOR_MAP.get(code)
            if known is None:
                lines.append(QuoteLine(**item.model_dump(), status="unmapped_color"))
                continue
            if part not in catalog:
                catalog[part] = self.search(part)
            matches = [
                e
                for e in catalog[part]
                if e.designId == part and e.facets.color.key == str(known.lego_id)
            ]
            if not matches:
                lines.append(
                    QuoteLine(
                        **item.model_dump(),
                        lego_color_id=known.lego_id,
                        status="not_found",
                    )
                )
                continue

            # Multiple exact elements can exist. Prefer an orderable element, then
            # one with a price, then the cheapest; never substitute another design.
            def rank(
                e: CatalogElement, quantity: int = quantity
            ) -> tuple[bool, bool, int, str]:
                limit = e.maxOrderQuantity if e.maxOrderQuantity is not None else 999
                return (
                    e.availability != "AVAILABLE" or quantity > limit,
                    e.price is None,
                    e.price.centAmount if e.price else 0,
                    e.id,
                )

            e = min(matches, key=rank)
            limit = e.maxOrderQuantity if e.maxOrderQuantity is not None else 999
            status = "available"
            if e.price is None:
                status = "price_unavailable"
            elif e.availability != "AVAILABLE":
                status = "out_of_stock"
            elif quantity > limit:
                status = "quantity_limit"
            lines.append(
                QuoteLine(
                    **item.model_dump(),
                    status=status,
                    element_id=e.id,
                    lego_color_id=known.lego_id,
                    name=e.name,
                    unit_price_cents=e.price.centAmount if e.price else None,
                    line_total_cents=e.price.centAmount * quantity if e.price else None,
                    max_order_quantity=limit,
                    delivery_channel=e.deliveryChannel,
                    url=f"https://www.lego.com/{self.locale}/pick-and-build/pick-a-brick?{urlencode({'query': e.id})}",
                )
            )
        complete = all(line.line_total_cents is not None for line in lines)
        subtotal = sum(line.line_total_cents or 0 for line in lines)
        return BuildQuote(
            locale=self.locale,
            currency=self.currency,
            checked_at=checked_at,
            complete=complete,
            purchasable=all(line.status == "available" for line in lines),
            total_quantity=sum(line.quantity for line in lines),
            priced_quantity=sum(
                line.quantity for line in lines if line.line_total_cents is not None
            ),
            known_subtotal_cents=subtotal,
            total_cents=subtotal if complete else None,
            lines=lines,
        )
