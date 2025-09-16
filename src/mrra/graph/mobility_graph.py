from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple
from itertools import groupby

import networkx as nx

from mrra.data.trajectory import TrajectoryBatch
from mrra.utils.geo import to_grid
from mrra.data.activity import ActivityExtractor, ActivityRecord
from mrra.analysis.activity_purpose import ActivityPurposeAssigner


@dataclass
class GraphConfig:
    grid_size_m: int = 200
    min_dwell_minutes: int = 10
    use_activities: bool = True


class MobilityGraph:
    """Build a MultiDiGraph from trajectories.

    Nodes:
      - user:u_<user_id>
      - loc:g_<gy>_<gx>
      - hour:h_<0-23>
      - dow:d_<0-6>
    Edges:
      - user -> loc (visit count)
      - loc -> loc (transition count)
      - loc <-> hour/dow (co-occurrence)
    """

    def __init__(
        self,
        tb: TrajectoryBatch,
        cfg: GraphConfig | None = None,
        *,
        purpose_assigner: ActivityPurposeAssigner | None = None,
        activities: list[ActivityRecord] | None = None,
        assume_purposes_assigned: bool = False,
    ):
        self.tb = tb
        self.cfg = cfg or GraphConfig()
        self.G = nx.MultiDiGraph()
        self._purpose_assigner = purpose_assigner
        self._activities = activities
        self._assume_purposes_assigned = bool(assume_purposes_assigned)
        self._build()

    def _loc_node(self, gy: int, gx: int) -> str:
        return f"g_{gy}_{gx}"

    def _user_node(self, user_id: str) -> str:
        return f"u_{user_id}"

    def _hour_node(self, hour: int) -> str:
        return f"h_{int(hour)}"

    def _dow_node(self, dow: int) -> str:
        return f"d_{int(dow)}"

    def _build(self) -> None:
        if self.cfg.use_activities:
            self._build_from_activities()
        else:
            self._build_from_points()

        # Aggregate top successors per loc
        for n, data in self.G.nodes(data=True):
            if data.get("type") == "loc":
                succ = []
                if n in self.G:
                    for nb in self.G.successors(n):
                        if self.G.nodes[nb].get("type") == "loc":
                            w = self.G[n][nb][0].get("weight", 1)
                            succ.append((nb, w))
                succ.sort(key=lambda x: x[1], reverse=True)
                self.G.nodes[n]["top_succ"] = succ[:5]

    def _build_from_points(self) -> None:
        df = self.tb.df
        grid_size = self.cfg.grid_size_m

        # derive grid indices
        gy_gx = df.apply(
            lambda r: to_grid(float(r.latitude), float(r.longitude), grid_size), axis=1
        )
        df = df.assign(_gy=[g[0] for g in gy_gx], _gx=[g[1] for g in gy_gx])

        for _, row in df.iterrows():
            u_node = self._user_node(row.user_id)
            g_node = self._loc_node(row._gy, row._gx)
            h_node = self._hour_node(row.hour)
            d_node = self._dow_node(row.dow)

            self.G.add_node(u_node, type="user", user_id=row.user_id)
            self.G.add_node(g_node, type="loc", gy=int(row._gy), gx=int(row._gx))
            self.G.add_node(h_node, type="hour", hour=int(row.hour))
            self.G.add_node(d_node, type="dow", dow=int(row.dow))

            w = (
                self.G[u_node][g_node][0]["weight"] + 1
                if self.G.has_edge(u_node, g_node, 0)
                else 1
            )
            self.G.add_edge(u_node, g_node, key=0, weight=w)

            for nn in (h_node, d_node):
                w1 = (
                    self.G[g_node][nn][0]["weight"] + 1
                    if self.G.has_edge(g_node, nn, 0)
                    else 1
                )
                w2 = (
                    self.G[nn][g_node][0]["weight"] + 1
                    if self.G.has_edge(nn, g_node, 0)
                    else 1
                )
                self.G.add_edge(g_node, nn, key=0, weight=w1)
                self.G.add_edge(nn, g_node, key=0, weight=w2)

        for user_id, udf in df.groupby("user_id"):
            udf = udf.sort_values("timestamp")
            prev: Tuple[int, int] | None = None
            for _, row in udf.iterrows():
                cur = (int(row._gy), int(row._gx))
                if prev is not None and prev != cur:
                    a = self._loc_node(*prev)
                    b = self._loc_node(*cur)
                    w = self.G[a][b][0]["weight"] + 1 if self.G.has_edge(a, b, 0) else 1
                    self.G.add_edge(a, b, key=0, weight=w, user=user_id)
                prev = cur

    def _build_from_activities(self) -> None:
        extractor = ActivityExtractor(
            self.tb,
            radius_m=self.cfg.grid_size_m,
            min_dwell_minutes=self.cfg.min_dwell_minutes,
            grid_size_m=self.cfg.grid_size_m,
        )
        if self._activities is not None:
            acts = self._activities
        else:
            acts = extractor.extract()
        # 给每个活动赋予“活动目的”：
        if not self._assume_purposes_assigned:
            assigner = self._purpose_assigner or ActivityPurposeAssigner(self.tb)
            try:
                acts = assigner.assign(acts)
            except Exception:
                pass
        # Add nodes and edges based on activities
        for ar in acts:
            u_node = self._user_node(ar.user_id)
            g_node = ar.place_id
            # parse gy,gx
            try:
                _, gy_s, gx_s = g_node.split("_")
                gy, gx = int(gy_s), int(gx_s)
            except Exception:
                gy = gx = 0
            h_node = self._hour_node(int(ar.start.hour))
            d_node = self._dow_node(int(ar.start.dayofweek))
            t_node = f"t_{int(ar.start.hour)}_{int(ar.start.dayofweek)}"
            p_node = f"p_{str(getattr(ar, 'purpose', '其他'))}"

            self.G.add_node(u_node, type="user", user_id=ar.user_id)
            self.G.add_node(
                g_node, type="loc", gy=gy, gx=gx, lat=ar.latitude, lon=ar.longitude
            )
            self.G.add_node(h_node, type="hour", hour=int(ar.start.hour))
            self.G.add_node(d_node, type="dow", dow=int(ar.start.dayofweek))
            self.G.add_node(
                t_node,
                type="timebin",
                hour=int(ar.start.hour),
                dow=int(ar.start.dayofweek),
            )
            self.G.add_node(
                p_node, type="purpose", name=str(getattr(ar, "purpose", "其他"))
            )

            # user -> loc weighted by duration
            w = (
                self.G[u_node][g_node][0].get("weight", 0) + ar.duration_min
                if self.G.has_edge(u_node, g_node, 0)
                else ar.duration_min
            )
            self.G.add_edge(
                u_node,
                g_node,
                key=0,
                weight=float(w),
                activity_type=ar.activity_type,
                activity_purpose=getattr(ar, "purpose", "unknown"),
            )

            # loc <-> temporal bins
            for nn in (h_node, d_node, t_node):
                w1 = (
                    self.G[g_node][nn][0].get("weight", 0) + ar.duration_min
                    if self.G.has_edge(g_node, nn, 0)
                    else ar.duration_min
                )
                w2 = (
                    self.G[nn][g_node][0].get("weight", 0) + ar.duration_min
                    if self.G.has_edge(nn, g_node, 0)
                    else ar.duration_min
                )
                self.G.add_edge(g_node, nn, key=0, weight=float(w1))
                self.G.add_edge(nn, g_node, key=0, weight=float(w2))

            # purpose 相关边
            # user -> purpose （分钟累计）
            wup = (
                self.G[u_node][p_node][0].get("weight", 0) + ar.duration_min
                if self.G.has_edge(u_node, p_node, 0)
                else ar.duration_min
            )
            self.G.add_edge(u_node, p_node, key=0, weight=float(wup))

            # purpose <-> loc （分钟累计）
            wpl = (
                self.G[p_node][g_node][0].get("weight", 0) + ar.duration_min
                if self.G.has_edge(p_node, g_node, 0)
                else ar.duration_min
            )
            wlp = (
                self.G[g_node][p_node][0].get("weight", 0) + ar.duration_min
                if self.G.has_edge(g_node, p_node, 0)
                else ar.duration_min
            )
            self.G.add_edge(p_node, g_node, key=0, weight=float(wpl))
            self.G.add_edge(g_node, p_node, key=0, weight=float(wlp))

            # purpose <-> hour/dow/timebin （分钟累计）
            for nn in (h_node, d_node, t_node):
                w1 = (
                    self.G[p_node][nn][0].get("weight", 0) + ar.duration_min
                    if self.G.has_edge(p_node, nn, 0)
                    else ar.duration_min
                )
                w2 = (
                    self.G[nn][p_node][0].get("weight", 0) + ar.duration_min
                    if self.G.has_edge(nn, p_node, 0)
                    else ar.duration_min
                )
                self.G.add_edge(p_node, nn, key=0, weight=float(w1))
                self.G.add_edge(nn, p_node, key=0, weight=float(w2))

        # transitions between activities per user
        acts_sorted = sorted(acts, key=lambda r: (r.user_id, r.start))
        for uid, group in groupby(acts_sorted, key=lambda r: r.user_id):
            prev_place: Optional[str] = None
            prev_purpose: Optional[str] = None
            for ar in list(group):
                cur_place = ar.place_id
                cur_purpose_node = f"p_{str(getattr(ar, 'purpose', '其他'))}"
                if prev_place and prev_place != cur_place:
                    w = (
                        self.G[prev_place][cur_place][0].get("weight", 0) + 1
                        if self.G.has_edge(prev_place, cur_place, 0)
                        else 1
                    )
                    self.G.add_edge(
                        prev_place, cur_place, key=0, weight=float(w), user=uid
                    )
                if prev_purpose and prev_purpose != cur_purpose_node:
                    wp = (
                        self.G[prev_purpose][cur_purpose_node][0].get("weight", 0) + 1
                        if self.G.has_edge(prev_purpose, cur_purpose_node, 0)
                        else 1
                    )
                    self.G.add_edge(
                        prev_purpose,
                        cur_purpose_node,
                        key=0,
                        weight=float(wp),
                        user=uid,
                    )
                prev_place = cur_place
                prev_purpose = cur_purpose_node
