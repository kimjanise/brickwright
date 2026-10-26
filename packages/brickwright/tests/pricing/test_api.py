import httpx
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from brickwright.pricing import PickABrickClient
from brickwright.pricing.api import app, get_client


@pytest.fixture
def api():
    row = {
        "id": "300121",
        "designId": "3001",
        "name": "BRICK 2X4",
        "availability": "AVAILABLE",
        "deliveryChannel": "pab",
        "facets": {"color": {"key": "21", "name": "Bright Red"}},
        "price": {"centAmount": 21, "currencyCode": "USD"},
    }

    def override():
        with PickABrickClient(
            http=httpx.Client(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(
                        200,
                        json={
                            "data": {
                                "searchElements": {
                                    "results": [row],
                                    "total": 1,
                                    "count": 1,
                                }
                            }
                        },
                    )
                )
            )
        ) as pab:
            yield pab

    app.dependency_overrides[get_client] = override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_bom_endpoint(api):
    res = api.post(
        "/api/pick-a-brick/quote",
        json={"items": [{"ldraw_id": "3001", "color_code": 4, "quantity": 10}]},
    )
    assert res.status_code == 200
    assert res.json()["total_cents"] == 210


def test_ldraw_endpoint(api):
    res = api.post(
        "/api/pick-a-brick/quote/ldraw",
        json={"ldraw": "1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat"},
    )
    assert res.status_code == 200
    assert res.json()["total_cents"] == 21


def test_search_endpoint(api):
    res = api.get("/api/pick-a-brick/search", params={"query": "3001"})
    assert res.status_code == 200
    assert res.json()["elements"][0]["id"] == "300121"


def test_invalid_bom_and_incomplete_ldraw_are_rejected(api):
    assert api.post("/api/pick-a-brick/quote", json={"items": []}).status_code == 422
    assert (
        api.post(
            "/api/pick-a-brick/quote",
            json={"items": [{"ldraw_id": "3001", "color_code": 4, "quantity": -1}]},
        ).status_code
        == 422
    )
    assert (
        api.post(
            "/api/pick-a-brick/quote/ldraw",
            json={"ldraw": "1 4 0 0 0 1 0 0 0 1 0 0 0 1 missing.dat"},
        ).status_code
        == 422
    )


def test_upstream_errors_are_502(api):
    def override():
        with PickABrickClient(
            http=httpx.Client(
                transport=httpx.MockTransport(lambda r: httpx.Response(403))
            )
        ) as pab:
            yield pab

    app.dependency_overrides[get_client] = override
    res = api.get("/api/pick-a-brick/search", params={"query": "3001"})
    assert res.status_code == 502 and "403" in res.json()["detail"]


def test_unsupported_locale_is_rejected():
    with TestClient(app) as client:
        assert (
            client.get("/api/pick-a-brick/search?query=3001&locale=xx-zz").status_code
            == 422
        )
