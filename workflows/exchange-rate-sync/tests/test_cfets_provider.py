import json
from datetime import date
from pathlib import Path

import pytest


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "cfets_history.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_parse_rates_falls_back_to_latest_published_date():
    from service.exchange_rate_service import parse_cfets_history

    result = parse_cfets_history(
        load_fixture(),
        requested_date=date(2026, 7, 12),
        currencies=["EUR", "USD", "JPY", "HKD", "SGD", "CAD"],
    )

    assert result.source_date == date(2026, 7, 10)
    assert [rate.from_currency for rate in result.rates] == [
        "EUR",
        "USD",
        "JPY",
        "HKD",
        "SGD",
        "CAD",
    ]
    assert result.rates[0].rate == 7.7712


def test_parse_rates_preserves_jpy_factor():
    from service.exchange_rate_service import parse_cfets_history

    result = parse_cfets_history(
        load_fixture(),
        requested_date=date(2026, 7, 10),
        currencies=["JPY"],
    )

    rate = result.rates[0]
    assert rate.rate == 4.1876
    assert rate.from_factor == 100
    assert rate.to_factor == 1
    assert rate.source_pair == "100JPY/CNY"


def test_parse_rates_fails_when_a_requested_currency_is_missing():
    from service.exchange_rate_service import ProviderDataError
    from service.exchange_rate_service import parse_cfets_history

    payload = load_fixture()
    payload["data"]["searchlist"] = ["USD/CNY"]
    payload["records"][1]["values"] = ["6.7989"]

    with pytest.raises(ProviderDataError, match="EUR"):
        parse_cfets_history(
            payload,
            requested_date=date(2026, 7, 10),
            currencies=["USD", "EUR"],
        )


def test_parse_rates_rejects_provider_error():
    from service.exchange_rate_service import ProviderDataError
    from service.exchange_rate_service import parse_cfets_history

    payload = load_fixture()
    payload["head"]["rep_code"] = "500"
    payload["head"]["rep_message"] = "provider unavailable"

    with pytest.raises(ProviderDataError, match="provider unavailable"):
        parse_cfets_history(
            payload,
            requested_date=date(2026, 7, 10),
            currencies=["USD"],
        )
