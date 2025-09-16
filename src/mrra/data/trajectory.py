from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List

import pandas as pd


REQUIRED_COLUMNS = ["user_id", "timestamp", "latitude", "longitude"]


def _validate_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"TrajectoryBatch requires columns: {REQUIRED_COLUMNS}, missing: {missing}"
        )


def _validate_latlon(df: pd.DataFrame) -> None:
    lat_ok = df["latitude"].between(-90.0, 90.0)
    lon_ok = df["longitude"].between(-180.0, 180.0)
    if not bool(lat_ok.all() and lon_ok.all()):
        bad = df.loc[
            ~(lat_ok & lon_ok), ["user_id", "timestamp", "latitude", "longitude"]
        ]
        raise ValueError(
            f"Found illegal latitude/longitude values in rows:\n{bad.head(5)}"
        )


@dataclass
class TrajectoryBatch:
    """Normalized batch of mobility trajectories.

    - Ensures timestamp type, sorting and indexing
    - Provides convenience accessors
    """

    df: pd.DataFrame
    tz: Optional[str] = None

    def __post_init__(self):
        _validate_columns(self.df)
        df = self.df.copy()
        # Parse timestamp
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        if df["timestamp"].isna().any():
            raise ValueError(
                "Failed to parse some timestamps; please ensure ISO format or pandas-parsable strings."
            )
        if self.tz:
            # Convert to target timezone while keeping UTC internally if needed
            df["timestamp_local"] = df["timestamp"].dt.tz_convert(self.tz)
        else:
            df["timestamp_local"] = df["timestamp"]

        _validate_latlon(df)
        df = df.sort_values(["user_id", "timestamp"]).reset_index(drop=True)

        # Derived columns
        df["hour"] = df["timestamp_local"].dt.hour.astype(int)
        df["dow"] = df["timestamp_local"].dt.dayofweek.astype(int)

        self.df = df

    # Convenience views
    def users(self) -> List[str]:
        return list(self.df["user_id"].drop_duplicates().tolist())

    def for_user(self, user_id: str) -> pd.DataFrame:
        return self.df[self.df["user_id"] == user_id].copy()

    def slice_by_date(self, user_id: str, date: str) -> pd.DataFrame:
        # date: YYYY-MM-DD in local tz (timestamp_local)
        d = pd.to_datetime(date).date()
        sdf = self.for_user(user_id)
        mask = sdf["timestamp_local"].dt.date == d
        return sdf[mask].copy()
