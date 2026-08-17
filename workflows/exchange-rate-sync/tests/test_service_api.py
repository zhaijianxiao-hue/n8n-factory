from datetime import date

from fastapi.testclient import TestClient


def test_health_endpoint():
    from service.exchange_rate_service import app

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "exchange-rate-sync",
        "version": "0.1.0",
        "port": 8770,
        "provider": "CFETS",
    }


def test_resolve_endpoint_returns_normalized_rates(monkeypatch):
    from service import exchange_rate_service as service

    async def fake_fetch(requested_date, currencies, lookback_days):
        assert requested_date == date(2026, 7, 12)
        assert currencies == ["USD", "JPY"]
        assert lookback_days == 10
        return service.ParsedRates(
            source_date=date(2026, 7, 10),
            rates=[
                service.ExchangeRate(
                    from_currency="USD",
                    rate=6.7989,
                    from_factor=1,
                    source_pair="USD/CNY",
                ),
                service.ExchangeRate(
                    from_currency="JPY",
                    rate=4.1876,
                    from_factor=100,
                    source_pair="100JPY/CNY",
                ),
            ],
        )

    monkeypatch.setattr(service, "fetch_cfets_rates", fake_fetch)
    response = TestClient(service.app).post(
        "/rates/resolve",
        json={
            "requested_date": "2026-07-12",
            "currencies": ["usd", "JPY"],
            "lookback_days": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert body["provider"] == "CFETS"
    assert body["source_date"] == "2026-07-10"
    assert body["rates"][1]["from_factor"] == 100
    assert body["warnings"] == [
        "requested_date 2026-07-12 used source_date 2026-07-10"
    ]


def test_resolve_endpoint_rejects_unsupported_currency():
    from service.exchange_rate_service import app

    response = TestClient(app).post(
        "/rates/resolve",
        json={"requested_date": "2026-07-10", "currencies": ["BTC"]},
    )

    assert response.status_code == 422


def test_resolve_endpoint_maps_provider_error_to_bad_gateway(monkeypatch):
    from service import exchange_rate_service as service

    async def fake_fetch(requested_date, currencies, lookback_days):
        raise service.ProviderDataError("CFETS returned no published rates")

    monkeypatch.setattr(service, "fetch_cfets_rates", fake_fetch)
    response = TestClient(service.app).post(
        "/rates/resolve",
        json={"requested_date": "2026-07-12", "currencies": ["USD"]},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "CFETS returned no published rates"
