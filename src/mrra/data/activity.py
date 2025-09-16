from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd

from .trajectory import TrajectoryBatch
from mrra.utils.geo import haversine_distance, to_grid


@dataclass
class ActivityRecord:
    user_id: str
    place_id: str
    latitude: float
    longitude: float
    start: pd.Timestamp
    end: pd.Timestamp
    duration_min: float
    activity_type: str = "other"  # home/work/other
    # 活动目的（例如：居住、工作、用餐、购物、娱乐、医疗、锻炼、社交、上学、通勤中转、其他）
    purpose: str = "unknown"


class ActivityExtractor:
    """Extract activity episodes (stays) from raw trajectory points.

    Heuristic: cluster consecutive points within radius and small time gaps,
    only keep clusters with minimal dwell duration.
    """

    def __init__(
        self,
        tb: TrajectoryBatch,
        *,
        radius_m: int = 200,
        min_dwell_minutes: int = 10,
        max_gap_minutes: int = 30,
        grid_size_m: int = 200,
        method: str = "radius",  # "radius" or "grid"
    ) -> None:
        self.tb = tb
        self.radius_m = radius_m
        self.min_dwell_minutes = min_dwell_minutes
        self.max_gap_minutes = max_gap_minutes
        self.grid_size_m = grid_size_m
        self.method = method

    def extract(self, user_id: Optional[str] = None) -> List[ActivityRecord]:
        users = [user_id] if user_id else self.tb.users()
        all_records: List[ActivityRecord] = []
        for uid in users:
            udf = self.tb.for_user(uid)
            if udf.empty:
                continue
            recs = self._extract_for_user(udf)
            # classify types
            for r in recs:
                r.activity_type = self._classify_type(r, uid)
            all_records.extend(recs)
        return all_records

    def _extract_for_user(self, df: pd.DataFrame) -> List[ActivityRecord]:
        if self.method == "grid":
            return self._extract_by_grid(df)
        points = df[["timestamp_local", "latitude", "longitude"]].to_records(
            index=False
        )
        cluster_pts: List[Tuple[pd.Timestamp, float, float]] = []
        start_ts: Optional[pd.Timestamp] = None
        end_ts: Optional[pd.Timestamp] = None
        records: List[ActivityRecord] = []

        def _finalize_cluster() -> None:
            nonlocal cluster_pts, start_ts, end_ts, records
            if not cluster_pts or start_ts is None or end_ts is None:
                cluster_pts = []
                start_ts = None
                end_ts = None
                return
            duration = (end_ts - start_ts).total_seconds() / 60.0
            if duration < self.min_dwell_minutes:
                cluster_pts = []
                start_ts = None
                end_ts = None
                return
            lat = sum(p[1] for p in cluster_pts) / len(cluster_pts)
            lon = sum(p[2] for p in cluster_pts) / len(cluster_pts)
            gy, gx = to_grid(lat, lon, self.grid_size_m)
            place_id = f"g_{gy}_{gx}"
            records.append(
                ActivityRecord(
                    user_id=str(df.iloc[0]["user_id"]),
                    place_id=place_id,
                    latitude=float(lat),
                    longitude=float(lon),
                    start=start_ts,
                    end=end_ts,
                    duration_min=float(duration),
                )
            )
            cluster_pts = []
            start_ts = None
            end_ts = None

        last_ts: Optional[pd.Timestamp] = None
        # Note: last_lat and last_lon removed as they were unused
        for ts, lat, lon in points:
            if last_ts is not None:
                gap = (ts - last_ts).total_seconds() / 60.0
                if gap > self.max_gap_minutes:
                    # large gap, finalize current cluster
                    _finalize_cluster()
            # update cluster membership
            if not cluster_pts:
                cluster_pts = [(ts, float(lat), float(lon))]
                start_ts = ts
                end_ts = ts
            else:
                # distance to current cluster centroid
                c_lat = sum(p[1] for p in cluster_pts) / len(cluster_pts)
                c_lon = sum(p[2] for p in cluster_pts) / len(cluster_pts)
                d = haversine_distance(c_lat, c_lon, float(lat), float(lon)) * 1000.0
                if d <= self.radius_m:
                    cluster_pts.append((ts, float(lat), float(lon)))
                    end_ts = ts
                else:
                    # finalize and start new cluster
                    _finalize_cluster()
                    cluster_pts = [(ts, float(lat), float(lon))]
                    start_ts = ts
                    end_ts = ts

            last_ts = ts
            # Note: last_lat and last_lon could be used for future enhancements
            _ = float(lat)  # last_lat
            _ = float(lon)  # last_lon

        # finalize tail
        _finalize_cluster()
        return records

    def _extract_by_grid(self, df: pd.DataFrame) -> List[ActivityRecord]:
        # Consecutive points in the same grid cell within gaps form an activity
        gy_gx = df.apply(
            lambda r: to_grid(float(r.latitude), float(r.longitude), self.grid_size_m),
            axis=1,
        )
        df = df.assign(_gy=[g[0] for g in gy_gx], _gx=[g[1] for g in gy_gx])
        records: List[ActivityRecord] = []
        cur_cell: Tuple[int, int] | None = None
        start_ts: pd.Timestamp | None = None
        end_ts: pd.Timestamp | None = None
        lat_sum = 0.0
        lon_sum = 0.0
        cnt = 0
        last_ts: pd.Timestamp | None = None

        def _finalize():
            nonlocal cur_cell, start_ts, end_ts, lat_sum, lon_sum, cnt
            if cur_cell is None or start_ts is None or end_ts is None:
                return
            dur = (end_ts - start_ts).total_seconds() / 60.0
            if dur >= self.min_dwell_minutes:
                lat = lat_sum / max(cnt, 1)
                lon = lon_sum / max(cnt, 1)
                place_id = f"g_{cur_cell[0]}_{cur_cell[1]}"
                records.append(
                    ActivityRecord(
                        user_id=str(df.iloc[0]["user_id"]),
                        place_id=place_id,
                        latitude=float(lat),
                        longitude=float(lon),
                        start=start_ts,
                        end=end_ts,
                        duration_min=float(dur),
                    )
                )
            cur_cell = None
            start_ts = None
            end_ts = None
            lat_sum = lon_sum = 0.0
            cnt = 0

        for _, row in df.iterrows():
            ts = row["timestamp_local"]
            cell = (int(row["_gy"]), int(row["_gx"]))
            if last_ts is not None:
                gap = (ts - last_ts).total_seconds() / 60.0
                if gap > self.max_gap_minutes:
                    _finalize()
            if cur_cell is None:
                cur_cell = cell
                start_ts = ts
                end_ts = ts
                lat_sum = float(row["latitude"])
                lon_sum = float(row["longitude"])
                cnt = 1
            else:
                if cell == cur_cell:
                    end_ts = ts
                    lat_sum += float(row["latitude"])
                    lon_sum += float(row["longitude"])
                    cnt += 1
                else:
                    _finalize()
                    cur_cell = cell
                    start_ts = ts
                    end_ts = ts
                    lat_sum = float(row["latitude"])
                    lon_sum = float(row["longitude"])
                    cnt = 1
            last_ts = ts

        _finalize()
        return records

    def _classify_type(self, r: ActivityRecord, user_id: str) -> str:
        # Simple heuristic: night long stays -> home; weekday daytime long stays -> work
        start_h = int(r.start.hour)
        end_h = int(r.end.hour)
        dow = int(r.start.dayofweek)
        dur = r.duration_min
        if dur >= 240 and (start_h >= 22 or start_h <= 6):  # >=4h night stay
            return "home"
        if (
            dur >= 240
            and (dow in (0, 1, 2, 3, 4))
            and (9 <= start_h <= 11 or 12 <= end_h <= 19)
        ):
            return "work"
        return "other"

    @staticmethod
    def to_dataframe(records: List[ActivityRecord]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "user_id": r.user_id,
                    "place_id": r.place_id,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "start": r.start,
                    "end": r.end,
                    "duration_min": r.duration_min,
                    "activity_type": r.activity_type,
                    "purpose": r.purpose,
                }
                for r in records
            ]
        )

    @staticmethod
    def from_dataframe(df: pd.DataFrame) -> List[ActivityRecord]:
        recs: List[ActivityRecord] = []
        if df is None or df.empty:
            return recs
        for _, row in df.iterrows():
            recs.append(
                ActivityRecord(
                    user_id=str(row.get("user_id")),
                    place_id=str(row.get("place_id")),
                    latitude=float(row.get("latitude")),
                    longitude=float(row.get("longitude")),
                    start=pd.to_datetime(row.get("start"), utc=True),
                    end=pd.to_datetime(row.get("end"), utc=True),
                    duration_min=float(row.get("duration_min", 0.0)),
                    activity_type=str(row.get("activity_type", "other")),
                    purpose=str(row.get("purpose", "unknown")),
                )
            )
        return recs
