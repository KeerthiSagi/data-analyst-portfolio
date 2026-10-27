"""Load, standardise and validate the transaction dataset.

The loader never writes to the source file and never falls back to
synthetic data: if the dataset cannot be found or fails validation, it
raises an error that explains what went wrong.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from cause import config


class DataSourceError(Exception):
    """The dataset could not be found or read."""


class DataValidationError(Exception):
    """The dataset was read but is not usable for analysis."""


# ------------------------------------------------------------------
# Locating and reading the file
# ------------------------------------------------------------------

def candidate_paths(explicit_path: str | os.PathLike | None = None) -> list[Path]:
    """Return the places the loader will look, in priority order."""
    paths: list[Path] = []
    if explicit_path:
        paths.append(Path(explicit_path).expanduser())
    env_value = os.environ.get(config.DATA_PATH_ENV_VAR, "").strip()
    if env_value:
        paths.append(Path(env_value).expanduser())
    paths.extend(config.DEFAULT_DATA_PATHS)
    return paths


def resolve_data_path(explicit_path: str | os.PathLike | None = None) -> Path:
    """Return the first existing dataset path, or raise DataSourceError.

    An explicit path or environment variable that points to a missing file
    is an error rather than a reason to silently try the defaults.
    """
    if explicit_path:
        return _require_file(Path(explicit_path).expanduser(), "explicit path")

    env_value = os.environ.get(config.DATA_PATH_ENV_VAR, "").strip()
    if env_value:
        return _require_file(
            Path(env_value).expanduser(), f"{config.DATA_PATH_ENV_VAR} environment variable"
        )

    for path in config.DEFAULT_DATA_PATHS:
        if path.is_file():
            return path

    checked = "\n".join(f"  - {p}" for p in config.DEFAULT_DATA_PATHS)
    raise DataSourceError(
        "Global Superstore dataset not found. Looked in:\n"
        f"{checked}\n"
        f"Set {config.DATA_PATH_ENV_VAR} to the dataset path, or copy "
        f"{config.DATASET_FILENAME} into {config.LOCAL_DATA_PATH.parent}."
    )


def _require_file(path: Path, source: str) -> Path:
    if not path.is_file():
        raise DataSourceError(f"Dataset not found at {path} (from {source}).")
    if path.suffix.lower() not in config.SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(config.SUPPORTED_EXTENSIONS))
        raise DataSourceError(f"Unsupported file type '{path.suffix}' at {path}. Use one of: {allowed}.")
    return path


def read_raw(path: Path) -> pd.DataFrame:
    """Read the file as-is (read-only)."""
    try:
        if path.suffix.lower() == ".csv":
            return pd.read_csv(path)
        return pd.read_excel(path)
    except Exception as exc:  # pragma: no cover - depends on file contents
        raise DataSourceError(f"Could not read dataset at {path}: {exc}") from exc


# ------------------------------------------------------------------
# Standardising
# ------------------------------------------------------------------

def _normalise_header(name: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename known source headers to snake_case names; keep others unchanged."""
    rename = {}
    for col in df.columns:
        target = config.COLUMN_ALIASES.get(_normalise_header(col))
        if target and target not in rename.values():
            rename[col] = target
    return df.rename(columns=rename)


def build_order_key(df: pd.DataFrame) -> pd.Series:
    """Composite transaction key: Order ID + Customer ID + Order Date.

    Order IDs alone are reused by different customers on different dates
    in Global Superstore, so the ID by itself undercounts transactions.
    """
    date_part = pd.to_datetime(df["order_date"]).dt.strftime("%Y-%m-%d")
    return (
        df["order_id"].astype(str)
        + "|"
        + df["customer_id"].astype(str)
        + "|"
        + date_part
    )


# ------------------------------------------------------------------
# Validation report
# ------------------------------------------------------------------

@dataclass
class OrderKeyCheck:
    """Evidence that the composite key identifies single transactions."""

    order_rows: int
    distinct_order_ids: int
    distinct_order_keys: int
    reused_order_ids: int
    # attribute -> number of keys that have more than one value for it
    inconsistent_attributes: dict[str, int]

    @property
    def is_consistent(self) -> bool:
        return all(count == 0 for count in self.inconsistent_attributes.values())


@dataclass
class ValidationReport:
    source_path: str
    row_count: int
    date_min: pd.Timestamp | None
    date_max: pd.Timestamp | None
    order_key: OrderKeyCheck | None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def check_order_key(df: pd.DataFrame) -> OrderKeyCheck:
    """Compare Order ID with the composite key and check order-level consistency."""
    key = config.ORDER_KEY_COLUMN
    ids_per_key_group = df.groupby("order_id")[key].nunique()
    attributes = [c for c in config.ORDER_LEVEL_ATTRIBUTES if c in df.columns]
    inconsistent = {}
    if attributes:
        per_key = df.groupby(key)[attributes].nunique(dropna=False)
        inconsistent = {col: int((per_key[col] > 1).sum()) for col in attributes}
    return OrderKeyCheck(
        order_rows=len(df),
        distinct_order_ids=int(df["order_id"].nunique()),
        distinct_order_keys=int(df[key].nunique()),
        reused_order_ids=int((ids_per_key_group > 1).sum()),
        inconsistent_attributes=inconsistent,
    )


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

@dataclass
class LoadedDataset:
    data: pd.DataFrame
    report: ValidationReport


def prepare_dataset(raw: pd.DataFrame, source_path: str = "<in-memory>") -> LoadedDataset:
    """Standardise, clean and validate a raw frame.

    Raises DataValidationError when the data cannot support analysis.
    Non-blocking problems are recorded as warnings on the report.
    """
    errors: list[str] = []
    warnings: list[str] = []

    df = standardize_columns(raw.copy())

    missing = [c for c in config.REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise DataValidationError(
            f"Dataset at {source_path} is missing required columns: {', '.join(missing)}. "
            f"Found: {', '.join(map(str, raw.columns))}."
        )
    if df.empty:
        raise DataValidationError(f"Dataset at {source_path} has no rows.")

    # Dates: drop time-of-day so period filters work on calendar days.
    for col in config.DATE_COLUMNS:
        if col in df.columns:
            # format="mixed" accepts date-only and date-time strings in one column.
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            bad = int(parsed.isna().sum() - df[col].isna().sum())
            if bad:
                warnings.append(f"{bad:,} value(s) in '{col}' could not be read as dates.")
            df[col] = parsed.dt.normalize()

    missing_dates = int(df["order_date"].isna().sum())
    if missing_dates:
        errors.append(f"{missing_dates:,} row(s) have no usable order date.")

    # Numbers
    for col in config.NUMERIC_COLUMNS:
        if col in df.columns:
            parsed = pd.to_numeric(df[col], errors="coerce")
            bad = int(parsed.isna().sum() - df[col].isna().sum())
            if bad:
                errors.append(f"{bad:,} value(s) in '{col}' are not numeric.")
            df[col] = parsed.astype(float)
    for col in ("sales", "profit"):
        nulls = int(df[col].isna().sum())
        if nulls:
            errors.append(f"{nulls:,} row(s) have no '{col}' value.")

    # Identifiers
    for col in ("order_id", "customer_id"):
        nulls = int(df[col].isna().sum())
        if nulls:
            errors.append(f"{nulls:,} row(s) have no '{col}'.")

    if errors:
        raise DataValidationError(
            f"Dataset at {source_path} failed validation:\n- " + "\n- ".join(errors)
        )

    # Text dimensions: trim, and label blanks explicitly instead of dropping rows.
    text_cols = set(config.DIMENSIONS.values()) | set(config.ORDER_LEVEL_ATTRIBUTES)
    for col in sorted(text_cols - {config.MARKET_REGION_COLUMN} - set(config.DATE_COLUMNS)):
        if col in df.columns:
            cleaned = df[col].astype("string").str.strip()
            blanks = int((cleaned.isna() | (cleaned == "")).sum())
            if blanks and col in config.DIMENSIONS.values():
                warnings.append(f"{blanks:,} row(s) have no '{col}'; labelled '{config.MISSING_LABEL}'.")
            df[col] = cleaned.mask(cleaned.isna() | (cleaned == ""), config.MISSING_LABEL).astype(str)

    df[config.MARKET_REGION_COLUMN] = df["market"] + " · " + df["region"]
    df[config.ORDER_KEY_COLUMN] = build_order_key(df)

    # Informational checks
    non_positive_sales = int((df["sales"] <= 0).sum())
    if non_positive_sales:
        warnings.append(
            f"{non_positive_sales:,} row(s) have sales of zero or less; kept as recorded."
        )
    if "ship_date" in df.columns:
        early = int((df["ship_date"] < df["order_date"]).sum())
        if early:
            warnings.append(f"{early:,} row(s) ship before they were ordered.")
    if "row_id" in df.columns and not df["row_id"].is_unique:
        warnings.append("Row IDs are not unique.")

    key_check = check_order_key(df)
    if key_check.reused_order_ids:
        warnings.append(
            f"{key_check.reused_order_ids:,} Order ID(s) are reused across different "
            "customers or dates; orders are counted with the composite key "
            "(Order ID + Customer ID + Order Date)."
        )
    if not key_check.is_consistent:
        bad = {k: v for k, v in key_check.inconsistent_attributes.items() if v}
        warnings.append(
            "Some composite order keys have conflicting order-level attributes: "
            + ", ".join(f"{k} ({v:,})" for k, v in bad.items())
        )

    report = ValidationReport(
        source_path=source_path,
        row_count=len(df),
        date_min=df["order_date"].min(),
        date_max=df["order_date"].max(),
        order_key=key_check,
        errors=[],
        warnings=warnings,
    )
    df = df.sort_values("order_date", kind="stable").reset_index(drop=True)
    return LoadedDataset(data=df, report=report)


def load_dataset(path: str | os.PathLike | None = None) -> LoadedDataset:
    """Find, read and validate the dataset. Never modifies the source file."""
    resolved = resolve_data_path(path)
    raw = read_raw(resolved)
    return prepare_dataset(raw, source_path=str(resolved))


def count_orders(df: pd.DataFrame) -> int:
    """Distinct transactions (composite key), not order rows."""
    if df.empty:
        return 0
    return int(df[config.ORDER_KEY_COLUMN].nunique())
