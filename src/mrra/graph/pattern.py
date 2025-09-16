from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from mrra.data.trajectory import TrajectoryBatch


@dataclass
class PatternGenerate:
    tb: TrajectoryBatch

    def long_short_patterns(self, user_id: str) -> Dict[str, Any]:
        """Compute simple long/short-term patterns and basic profile.

        Heuristics:
        - Home: frequent night-time cells (20-6h)
        - Work: frequent day-time weekday cells (9-18h, Mon-Fri)
        - Short-term: most recent transitions
        - Long-term: hour-of-day and dow preferences
        """
        df = self.tb.for_user(user_id)
        if df.empty:
            return {"long": [], "short": [], "profile": {}}

        # Home/work heuristics
        night = df[(df["hour"] >= 20) | (df["hour"] <= 6)]
        daywk = df[(df["hour"].between(9, 18)) & (df["dow"].between(0, 4))]

        def top_cell(sdf: pd.DataFrame) -> str | None:
            if sdf.empty:
                return None
            # use approximate lat/lon rounding for a cell signature
            cell = (
                sdf["latitude"].round(3).astype(str)
                + ","
                + sdf["longitude"].round(3).astype(str)
            )
            return cell.value_counts().idxmax()

        home = top_cell(night)
        work = top_cell(daywk)

        # Short-term transitions
        recent = df.tail(10)
        short = []
        for i in range(1, len(recent)):
            a = f"({recent.iloc[i - 1]['latitude']:.3f},{recent.iloc[i - 1]['longitude']:.3f})"
            b = f"({recent.iloc[i]['latitude']:.3f},{recent.iloc[i]['longitude']:.3f})"
            if a != b:
                short.append(f"最近从 {a} 迁移到 {b}")

        # Long-term hour/dow preferences
        long = []
        hour_pref = df["hour"].value_counts().sort_index()
        dow_pref = df["dow"].value_counts().sort_index()
        if not hour_pref.empty:
            peak_h = int(hour_pref.idxmax())
            long.append(f"常在 {peak_h}:00 附近活动")
        if not dow_pref.empty:
            peak_d = int(dow_pref.idxmax())
            long.append(f"在周{peak_d} 活动更频繁")

        profile = {"home": home, "work": work}
        return {"long": long, "short": short[-5:], "profile": profile}
