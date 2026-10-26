"""Pricing must never silently substitute a color or undercount a build."""

import json

import httpx
import pytest
from pydantic import ValidationError

from brickwright.pricing import BomItem, PickABrickClient, PricingError, bom_from_ldraw


def element(id="300121", design="3001", color="21", cents=21, **changes):
    return dict(
        id=id,
        designId=design,
        name="BRICK 2X4",
        maxOrderQuantity=None,
        deliveryChannel="pab",
        facets={"color": {"name": "Bright Red", "key": color}},
        price={"centAmount": cents, "currencyCode": "USD"},
        availability="AVAILABLE",
        **changes,
    )


def response(items, total=None):
    return {
        "data": {
            "searchElements": {
                "results": items,
                "total": len(items) if total is None else total,
                "count": len(items),
            }
        }
    }


def client(handler):
    return PickABrickClient(http=httpx.Client(transport=httpx.MockTransport(handler)))


def item(**changes):
    return BomItem.model_validate(
        {"ldraw_id": "3001", "color_code": 4, "quantity": 2} | changes
    )


def test_matches_exact_design_and_lego_color_and_counts_duplicates():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json=response(
                [
                    element(id="300123", color="23", cents=5),
                    element(id="3001021", design="30010", cents=2),
                    element(),
                ]
            ),
        )

    with client(handle) as pab:
        quote = pab.quote([item(), item(quantity=3)])
    assert len(requests) == 1
    assert quote.complete and quote.purchasable
    assert quote.total_cents == 105
    assert quote.lines[0].quantity == 5
    assert quote.lines[0].element_id == "300121"
    assert requests[0].headers["x-locale"] == "en-US"
    body = json.loads(requests[0].content)
    assert body["variables"]["input"]["availability"] == ["AVAILABLE", "OUT_OF_STOCK"]
    assert "availability" in body["query"] and "inStock" not in body["query"]


def test_missing_color_never_becomes_zero_or_a_full_total():
    with client(lambda r: httpx.Response(200, json=response([element()]))) as pab:
        quote = pab.quote([item(), item(color_code=1)])
    assert quote.total_cents is None
    assert quote.known_subtotal_cents == 42
    assert quote.priced_quantity == 2 and quote.total_quantity == 4
    assert quote.lines[1].status == "not_found"
    assert not quote.complete and not quote.purchasable


@pytest.mark.parametrize(
    "change,status",
    [
        ({"availability": "OUT_OF_STOCK"}, "out_of_stock"),
        ({"maxOrderQuantity": 1}, "quantity_limit"),
        ({"price": None}, "price_unavailable"),
    ],
)
def test_unavailable_and_limits(change, status):
    row = element() | change
    with client(lambda r: httpx.Response(200, json=response([row]))) as pab:
        quote = pab.quote([item()])
    assert quote.lines[0].status == status
    assert not quote.purchasable
    assert quote.complete == (status != "price_unavailable")


def test_unknown_color_and_decorated_part_are_not_guessed():
    calls = []

    def handle(r):
        calls.append(r)
        return httpx.Response(200, json=response([element()]))

    with client(handle) as pab:
        quote = pab.quote([item(color_code=9999), item(ldraw_id="3001p01")])
    assert quote.lines[0].status == "unmapped_color"
    assert quote.lines[1].status == "not_found"
    assert len(calls) == 1


def test_pages_are_followed_and_currency_is_checked():
    pages = []

    def handle(r):
        page = json.loads(r.content)["variables"]["input"]["page"]
        pages.append(page)
        return httpx.Response(
            200,
            json=response(
                [element(id="300123", color="23")] if page == 1 else [element()],
                total=2,
            ),
        )

    with client(handle) as pab:
        assert pab.quote([item()]).total_cents == 42
    assert pages == [1, 2]
    with (
        client(
            lambda r: httpx.Response(
                200,
                json=response(
                    [element() | {"price": {"centAmount": 21, "currencyCode": "EUR"}}]
                ),
            )
        ) as pab,
        pytest.raises(PricingError, match="currency"),
    ):
        pab.quote([item()])


@pytest.mark.parametrize(
    "payload",
    [
        {"errors": [{"message": "bad query"}]},
        {"data": None},
        response([element() | {"price": {"centAmount": -1, "currencyCode": "USD"}}]),
    ],
)
def test_invalid_upstream_is_not_a_quote(payload):
    with (
        client(lambda r: httpx.Response(200, json=payload)) as pab,
        pytest.raises(PricingError),
    ):
        pab.quote([item()])


@pytest.mark.parametrize("status", [403, 429, 500])
def test_http_errors_are_actionable(status):
    with (
        client(lambda r: httpx.Response(status, text="unavailable")) as pab,
        pytest.raises(PricingError, match=str(status)),
    ):
        pab.quote([item()])


def test_network_timeout_is_actionable():
    def handle(r):
        raise httpx.ReadTimeout("timeout", request=r)

    with client(handle) as pab, pytest.raises(PricingError, match="reach LEGO"):
        pab.quote([item()])


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True])
def test_reject_bad_quantities(quantity):
    with pytest.raises(ValidationError):
        item(quantity=quantity)


def test_reject_unsupported_locale_and_empty_build():
    with pytest.raises(ValueError, match="locale"):
        PickABrickClient(locale="xx-zz")
    with (
        client(lambda r: httpx.Response(200)) as pab,
        pytest.raises(ValueError, match="empty"),
    ):
        pab.quote([])


def test_ldraw_nested_models_inherit_color_and_multiply():
    text = """0 FILE main.ldr
1 4 0 0 0 1 0 0 0 1 0 0 0 1 sub.ldr
1 1 80 0 0 1 0 0 0 1 0 0 0 1 sub.ldr
0 FILE sub.ldr
1 16 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat
1 16 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat
"""
    bom = bom_from_ldraw(text)
    assert {(b.ldraw_id, b.color_code, b.quantity) for b in bom} == {
        ("3001", 4, 2),
        ("3001", 1, 2),
    }


def test_ldraw_rejects_missing_geometry_instead_of_underquoting():
    with pytest.raises(ValueError, match="incomplete"):
        bom_from_ldraw("1 4 0 0 0 1 0 0 0 1 0 0 0 1 nonexistent.dat")


def test_out_of_stock_element_can_have_no_delivery_channel():
    row = element() | {"deliveryChannel": None, "availability": "OUT_OF_STOCK"}
    with client(lambda r: httpx.Response(200, json=response([row]))) as pab:
        quote = pab.quote([item()])
    assert quote.total_cents == 42 and not quote.purchasable


def test_duplicate_lines_cannot_bypass_order_limit():
    with client(lambda r: httpx.Response(200, json=response([element()]))) as pab:
        quote = pab.quote([item(quantity=600), item(quantity=600)])
    assert quote.lines[0].quantity == 1200
    assert quote.lines[0].status == "quantity_limit"


def test_repeated_page_is_an_error_not_an_incomplete_match():
    with (
        client(
            lambda r: httpx.Response(200, json=response([element()], total=2))
        ) as pab,
        pytest.raises(PricingError, match="pagination"),
    ):
        pab.quote([item()])


def test_cheapest_orderable_exact_element_is_selected():
    rows = [
        element(id="1", cents=1) | {"availability": "OUT_OF_STOCK"},
        element(id="2", cents=30),
        element(id="3", cents=25),
    ]
    with client(lambda r: httpx.Response(200, json=response(rows))) as pab:
        quote = pab.quote([item()])
    assert quote.lines[0].element_id == "3"
    assert quote.total_cents == 50


def test_custom_color_cannot_masquerade_as_catalog_color():
    text = "0 !COLOUR Custom CODE 4 VALUE #00FF00 EDGE #333333\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat"
    with pytest.raises(ValueError, match="Custom color"):
        bom_from_ldraw(text)


def test_custom_transparency_cannot_be_priced_as_solid_red():
    text = "0 !COLOUR Custom CODE 4 VALUE #C91A09 EDGE #333333 ALPHA 128\n1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat"
    with pytest.raises(ValueError, match="Custom color"):
        bom_from_ldraw(text)


def test_raw_geometry_cannot_be_silently_ignored():
    text = "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n3 4 0 0 0 10 0 0 10 10 0"
    with pytest.raises(ValueError, match="geometry"):
        bom_from_ldraw(text)
