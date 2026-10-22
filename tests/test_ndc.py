import pytest

from ingestion.utils.ndc import extract_ndcs, normalize_ndc, product_key


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0409-4888-10", "00409488810"),  # 4-4-2
        ("12345-678-90", "12345067890"),  # 5-3-2
        ("12345-6789-1", "12345678901"),  # 5-4-1 -> package segment padded to 2
        ("65691-0090", "656910090"),  # product NDC
        ("0409-4888", "004094888"),
        ("abc-123", None),
        ("123456-1234-12", None),  # labeler too long
        ("12345", None),
    ],
)
def test_normalize(raw, expected):
    assert normalize_ndc(raw) == expected


def test_product_key_drops_package():
    assert product_key("0409-4888-10") == "004094888"


def test_extract_keyword_and_bare():
    text = "Vial, NDC 0409-4888-10; also 65691-0090 distributed. Lot 12345-6789-12-3"
    found = dict(extract_ndcs(text))
    assert found["00409488810"] is True
    assert found["656910090"] is False  # bare token, no keyword
    assert len(found) == 2  # the lot number is not picked up


def test_extract_deduplicates_and_handles_empty():
    assert extract_ndcs("NDC 0409-4888-10 and NDC: 0409-4888-10") == [("00409488810", True)]
    assert extract_ndcs("") == [] and extract_ndcs(None) == []


def test_extract_ignores_dates():
    assert extract_ndcs("Exp 10/29/2015 lot 2023-01-15") == []


def test_keyword_flag_if_any_occurrence_has_keyword():
    assert extract_ndcs("0409-4888-10 then NDC 0409-4888-10") == [("00409488810", True)]
