import numpy as np
import pandas as pd
import pytest

pytest.importorskip("statsmodels")

from analysis.precision import wilson
from analysis.risk_factors import design, holm, informative
from analysis.risk_score import set_auc


def test_wilson_matches_known_value():
    lo, hi = wilson(57, 100)
    assert round(lo, 3) == 0.472 and round(hi, 3) == 0.663


def test_wilson_stays_inside_zero_one_at_extremes():
    lo, hi = wilson(0, 20)
    assert lo == pytest.approx(0, abs=1e-12) and 0 < hi < 0.2


def test_holm_step_down_is_monotone_and_capped():
    adj = holm({"a": 0.01, "b": 0.04, "c": 0.03, "d": 0.5})
    assert adj["a"] == pytest.approx(0.04) and adj["c"] == pytest.approx(0.09)
    assert adj["b"] >= adj["c"] and max(adj.values()) <= 1.0


def test_set_auc_counts_wins_and_ties():
    df = pd.DataFrame({"set_id": ["s", "s", "s", "t", "t"], "role": ["case", "control", "control", "case", "control"]})
    auc = set_auc(df, [2.0, 1.0, 3.0, 1.0, 1.0])
    assert auc["s"] == 0.5 and auc["t"] == 0.5


def test_design_zeroes_terms_whose_window_predates_the_data():
    df = pd.DataFrame({
        "set_id": ["a", "a"], "role": ["case", "control"], "family_key": ["f1", "f2"],
        "as_of_date": pd.to_datetime(["2022-06-01", "2022-06-01"]),
        "n_suppliers": [1, 3], "approval_class": ["generic", "brand"], "is_injectable": [True, False],
        "therapeutic_group": ["oncology", "other"],
        "last_recall_product_date": pd.to_datetime(["2022-01-01", None]),
        "last_recall_ingredient_date": pd.to_datetime([None, None]),
        "last_warning_letter_date": pd.to_datetime(["2022-03-01", None]),
    })
    # Letters start 2021-01-05, so a 24 month window before 2022-06-01 is not covered: the letter term must be 0
    x = design(df, pd.Timestamp("2012-01-01"), pd.Timestamp("2021-01-05"))
    assert x.warning_letter.tolist() == [0.0, 0.0]
    assert x.recall_product.tolist() == [1.0, 0.0]
    assert x.sole_x_generic.tolist() == [1.0, 0.0]


def test_informative_drops_columns_without_within_set_variation():
    x = pd.DataFrame({"a": [1.0, 0.0, 1.0, 1.0], "b": [1.0, 1.0, 0.0, 0.0]})
    assert informative(x, pd.Series(["s", "s", "t", "t"])) == ["a"]
