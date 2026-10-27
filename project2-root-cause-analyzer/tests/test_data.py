import pandas as pd
import pytest

from cause import config
from cause.data import (
    DataSourceError,
    DataValidationError,
    check_order_key,
    count_orders,
    load_dataset,
    prepare_dataset,
    resolve_data_path,
    standardize_columns,
)
from tests.conftest import make_raw


# ------------------------------------------------------------------
# Locating the file
# ------------------------------------------------------------------

def test_explicit_missing_path_raises_and_does_not_fall_back(tmp_path):
    with pytest.raises(DataSourceError, match="Dataset not found"):
        resolve_data_path(tmp_path / "nope.xlsx")


def test_env_var_missing_path_raises(monkeypatch, tmp_path):
    monkeypatch.setenv(config.DATA_PATH_ENV_VAR, str(tmp_path / "missing.xlsx"))
    with pytest.raises(DataSourceError, match=config.DATA_PATH_ENV_VAR):
        resolve_data_path()


def test_env_var_path_is_used(monkeypatch, tmp_path, raw_orders):
    csv = tmp_path / "orders.csv"
    raw_orders.to_csv(csv, index=False)
    monkeypatch.setenv(config.DATA_PATH_ENV_VAR, str(csv))
    assert resolve_data_path() == csv
    loaded = load_dataset()
    assert loaded.report.source_path == str(csv)
    assert loaded.report.row_count == 5


def test_no_dataset_anywhere_raises_helpful_error(monkeypatch, tmp_path):
    monkeypatch.delenv(config.DATA_PATH_ENV_VAR, raising=False)
    monkeypatch.setattr(config, "DEFAULT_DATA_PATHS", (tmp_path / "a.xlsx", tmp_path / "b.xlsx"))
    with pytest.raises(DataSourceError) as exc:
        resolve_data_path()
    message = str(exc.value)
    assert "a.xlsx" in message and "b.xlsx" in message
    assert config.DATA_PATH_ENV_VAR in message


def test_unsupported_extension(tmp_path):
    bad = tmp_path / "orders.json"
    bad.write_text("{}")
    with pytest.raises(DataSourceError, match="Unsupported file type"):
        resolve_data_path(bad)


def test_loader_does_not_modify_source(tmp_path, raw_orders):
    csv = tmp_path / "orders.csv"
    raw_orders.to_csv(csv, index=False)
    before = csv.read_bytes(), csv.stat().st_mtime_ns
    load_dataset(csv)
    assert (csv.read_bytes(), csv.stat().st_mtime_ns) == before


# ------------------------------------------------------------------
# Standardising
# ------------------------------------------------------------------

@pytest.mark.parametrize("header", ["Order.ID", "Order ID", "order_id", "ORDER-ID"])
def test_header_variants_map_to_canonical(header):
    df = standardize_columns(pd.DataFrame(columns=[header, "Sub.Category"]))
    assert list(df.columns) == ["order_id", "sub_category"]


def test_unknown_columns_are_kept():
    df = standardize_columns(pd.DataFrame(columns=["Order.ID", "weeknum"]))
    assert "weeknum" in df.columns


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------

def test_missing_required_columns_raise(raw_orders):
    with pytest.raises(DataValidationError, match="profit"):
        prepare_dataset(raw_orders.drop(columns=["Profit"]))


def test_empty_frame_raises(raw_orders):
    with pytest.raises(DataValidationError, match="no rows"):
        prepare_dataset(raw_orders.iloc[0:0])


def test_non_numeric_sales_raise(raw_orders):
    raw = raw_orders.astype({"Sales": object})
    raw.loc[0, "Sales"] = "lots"
    with pytest.raises(DataValidationError, match="not numeric"):
        prepare_dataset(raw)


def test_unparseable_order_date_raises(raw_orders):
    raw = raw_orders.copy()
    raw.loc[0, "Order.Date"] = "not a date"
    with pytest.raises(DataValidationError, match="order date"):
        prepare_dataset(raw)


def test_dates_are_normalised_to_calendar_days(raw_orders):
    raw = raw_orders.copy()
    raw.loc[0, "Order.Date"] = "2014-01-05 17:45:00"
    raw.loc[1, "Order.Date"] = "2014-01-05 09:00:00"
    df = prepare_dataset(raw).data
    assert (df["order_date"] == df["order_date"].dt.normalize()).all()
    # Same order on the same day stays one transaction despite times.
    assert df.loc[df["order_id"] == "O-1", "order_key"].nunique() == 1


def test_blank_dimension_is_labelled_not_dropped(raw_orders):
    raw = raw_orders.copy()
    raw.loc[4, "Segment"] = "  "
    loaded = prepare_dataset(raw)
    assert len(loaded.data) == 5
    assert (loaded.data["segment"] == config.MISSING_LABEL).sum() == 1
    assert any("segment" in w for w in loaded.report.warnings)


def test_non_positive_sales_are_kept_with_warning(raw_orders):
    raw = raw_orders.copy()
    raw.loc[4, "Sales"] = 0
    loaded = prepare_dataset(raw)
    assert len(loaded.data) == 5
    assert any("sales of zero or less" in w for w in loaded.report.warnings)


def test_market_region_label_disambiguates_repeated_region_names(raw_orders):
    df = prepare_dataset(raw_orders).data
    central = df.loc[df["region"] == "Central", config.MARKET_REGION_COLUMN].unique()
    assert set(central) == {"US · Central", "EU · Central"}


# ------------------------------------------------------------------
# Composite order key
# ------------------------------------------------------------------

def test_order_rows_vs_distinct_orders(raw_orders):
    loaded = prepare_dataset(raw_orders)
    df = loaded.data
    assert len(df) == 5                      # order rows
    assert df["order_id"].nunique() == 3     # Order ID alone undercounts
    assert count_orders(df) == 4             # composite key transactions
    check = loaded.report.order_key
    assert check.distinct_order_ids == 3
    assert check.distinct_order_keys == 4
    assert check.reused_order_ids == 1
    assert check.is_consistent
    assert any("reused" in w for w in loaded.report.warnings)


def test_key_check_flags_conflicting_attributes(raw_orders):
    raw = raw_orders.copy()
    raw.loc[1, "Ship.Mode"] = "First Class"  # same key as row 0, different mode
    loaded = prepare_dataset(raw)
    check = loaded.report.order_key
    assert not check.is_consistent
    assert check.inconsistent_attributes["ship_mode"] == 1
    assert any("conflicting" in w for w in loaded.report.warnings)


def test_count_orders_empty_frame(raw_orders):
    df = prepare_dataset(raw_orders).data
    assert count_orders(df.iloc[0:0]) == 0


def test_check_order_key_on_single_line_orders(raw_orders):
    df = prepare_dataset(raw_orders.iloc[[0, 2, 4]]).data
    check = check_order_key(df)
    assert check.distinct_order_ids == check.distinct_order_keys == 3
    assert check.reused_order_ids == 0
