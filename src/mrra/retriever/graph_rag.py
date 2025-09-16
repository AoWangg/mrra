from __future__ import annotations

from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import numpy as np

try:
    from langchain_core.retrievers import BaseRetriever
    from langchain_core.documents import Document
except Exception:  # fallback for environments w/o langchain installed

    class BaseRetriever:  # type: ignore
        def invoke(self, *_args, **_kwargs):  # pragma: no cover - lightweight fallback
            raise ImportError("langchain-core is required for GraphRAGGenerate")

    @dataclass
    class Document:  # type: ignore
        page_content: str
        metadata: Dict[str, Any]


from mrra.graph.mobility_graph import MobilityGraph
from mrra.data.trajectory import TrajectoryBatch
from pydantic import Field, model_validator
import math


def _softmax(x: np.ndarray) -> np.ndarray:
    x = x - np.max(x)
    e = np.exp(x)
    return e / (e.sum() + 1e-12)


class GraphRAGGenerate(BaseRetriever):
    """Graph-based retriever operating on MobilityGraph.

    Query format example:
      {"user_id": "user_1", "t": "2023-01-02 09:00", "k": 8}
    """

    # Pydantic v1-style fields for BaseRetriever
    tb: TrajectoryBatch
    mobility_graph: Optional[MobilityGraph] = Field(default=None)
    k: int = 8
    max_hops: int = 2
    hour_weight: float = 0.5
    dow_weight: float = 0.3
    recent_weight: float = 0.2
    purpose_weight: float = 0.6

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _ensure_graph(self):  # type: ignore
        if (
            getattr(self, "mobility_graph", None) is None
            and getattr(self, "tb", None) is not None
        ):
            object.__setattr__(self, "mobility_graph", MobilityGraph(self.tb))
        return self

    # LangChain will call this under the hood
    def _get_relevant_documents(
        self, query: Dict[str, Any], *, run_manager=None
    ) -> List[Document]:
        return self._retrieve(query)

    async def _aget_relevant_documents(
        self, query: Dict[str, Any], *, run_manager=None
    ) -> List[Document]:
        return self._retrieve(query)

    # Allow direct programmatic usage
    def get_relevant_documents(self, query: Dict[str, Any]) -> List[Document]:
        return self._retrieve(query)

    def _retrieve(self, query: Dict[str, Any]) -> List[Document]:
        G = self.mobility_graph.G  # type: ignore
        user_id: str = query.get("user_id")
        k: int = int(query.get("k", self.k))

        # parse time context
        from pandas import to_datetime

        t = to_datetime(query.get("t")) if query.get("t") is not None else None
        hour = (
            int(t.tz_convert("UTC").hour if getattr(t, "tzinfo", None) else t.hour)
            if t is not None
            else None
        )
        dow = int(t.dayofweek) if t is not None else None

        # seed nodes
        seeds: List[str] = []
        u_node = f"u_{user_id}"
        if u_node in G:
            seeds.append(u_node)
        if hour is not None:
            h_node = f"h_{hour}"
            if h_node in G:
                seeds.append(h_node)
        if dow is not None:
            d_node = f"d_{dow}"
            if d_node in G:
                seeds.append(d_node)
        # optional purpose seeds (string or list of strings)
        purpose_q = query.get("purpose")
        if purpose_q is not None:
            if isinstance(purpose_q, str):
                purpose_vals = [purpose_q]
            elif isinstance(purpose_q, list):
                purpose_vals = [str(x) for x in purpose_q]
            else:
                purpose_vals = []
            for pv in purpose_vals:
                p_node = f"p_{pv}"
                if p_node in G:
                    seeds.append(p_node)

        # score candidate location nodes by random-walk-like weighted hops
        loc_scores: Dict[str, float] = {}
        for s in seeds:
            for nb in G.neighbors(s):
                if G.nodes[nb].get("type") == "loc":
                    w = G[s][nb][0].get("weight", 1.0)
                    # weight by seed type
                    if s.startswith("u_"):
                        factor = 1.0
                    elif s.startswith("h_"):
                        factor = self.hour_weight
                    elif s.startswith("d_"):
                        factor = self.dow_weight
                    elif s.startswith("p_"):
                        factor = self.purpose_weight
                    else:
                        factor = 0.5
                    loc_scores[nb] = loc_scores.get(nb, 0.0) + factor * float(w)

        # Add recency bias using last observed location for the user
        udf = self.tb.for_user(user_id)
        if not udf.empty:
            last = udf.iloc[-1]
            # approximate to nearest loc node signature used by graph builder
            from mrra.utils.geo import to_grid

            gy, gx = to_grid(
                float(last.latitude),
                float(last.longitude),
                self.mobility_graph.cfg.grid_size_m,
            )  # type: ignore
            last_node = f"g_{gy}_{gx}"
            if last_node in G:
                loc_scores[last_node] = (
                    loc_scores.get(last_node, 0.0) + 1.0 * self.recent_weight
                )

        if not loc_scores:
            return []

        # normalize scores and take top-k
        nodes = list(loc_scores.keys())
        vals = np.array([loc_scores[n] for n in nodes], dtype=float)
        probs = _softmax(vals)
        order = np.argsort(-probs)[:k]

        docs: List[Document] = []
        for idx in order:
            n = nodes[int(idx)]
            p = float(probs[int(idx)])
            node_data = G.nodes[n]
            # decode approximate lat/lon center from grid id by sampling connected edges to hours/dow is optional
            # We don't store exact lat/lon for grid nodes; embed grid indices in metadata
            gy = (
                int(node_data.get("gy", n.split("_")[1]))
                if "gy" in node_data
                else int(n.split("_")[1])
            )
            gx = (
                int(node_data.get("gx", n.split("_")[2]))
                if "gx" in node_data
                else int(n.split("_")[2])
            )
            # approximate lat/lon center for the grid cell (assumes 200m grid)
            grid_m = float(self.mobility_graph.cfg.grid_size_m)  # type: ignore
            m_per_deg_lat = 111_132.0
            lat_center = (float(gy) + 0.5) * (grid_m / m_per_deg_lat)
            m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat_center))
            lon_center = (float(gx) + 0.5) * (grid_m / m_per_deg_lon)
            docs.append(
                Document(
                    page_content=f"Candidate location node {n} with score {p:.4f}",
                    metadata={
                        "node": n,
                        "score": p,
                        "grid": {"gy": gy, "gx": gx},
                        "lat": lat_center,
                        "lon": lon_center,
                        "top_succ": node_data.get("top_succ", []),
                    },
                )
            )
        return docs
