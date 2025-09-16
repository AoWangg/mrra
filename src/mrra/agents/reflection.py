from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import logging

try:
    from langchain_core.runnables import Runnable
except Exception:  # pragma: no cover
    Runnable = object  # type: ignore


def _average_points(points: List[List[float]], weights: List[float]) -> List[float]:
    if not points:
        return [None, None]  # type: ignore
    ws = sum(weights) if sum(weights) > 0 else 1.0
    lat = sum(p[0] * w for p, w in zip(points, weights)) / ws
    lon = sum(p[1] * w for p, w in zip(points, weights)) / ws
    return [lat, lon]


@dataclass
class ReflectionOrchestrator(Runnable):
    subagents: Dict[str, Any]
    retriever: Any
    max_round: int = 3
    aggregator: str = "confidence_weighted_voting"

    def _compose_query(
        self, inputs: Dict[str, Any], state: Dict[str, Any]
    ) -> Dict[str, Any]:
        evid = [d.metadata for d in state.get("evidence", [])]
        # Build options from evidence docs
        options = []
        for m in evid:
            options.append(
                {
                    "id": m.get("node"),
                    "score": m.get("score"),
                    "lat": m.get("lat"),
                    "lon": m.get("lon"),
                    "grid": m.get("grid"),
                    "top_succ": m.get("top_succ", []),
                }
            )
        return {
            "task": inputs.get("task", "next_position"),
            "options": options,
            "evidence": evid,
            "history": state.get("history", []),
        }

    def _aggregate(self, state: Dict[str, Any], task: str) -> Dict[str, Any]:
        # Collect last-round outputs from subagents
        per_agent = state.get("history", [])[-1] if state.get("history") else {}

        # Build id -> coord mapping from evidence
        evid = [d.metadata for d in state.get("evidence", [])]
        id2coord: Dict[str, List[float]] = {}
        for m in evid:
            nid = m.get("node")
            if nid and m.get("lat") is not None and m.get("lon") is not None:
                id2coord[str(nid)] = [float(m["lat"]), float(m["lon"])]

        # Gather selections / paths
        selections: List[str] = []
        sel_weights: List[float] = []
        path_ids: List[List[str]] = []
        path_weights: List[float] = []
        for _, out in per_agent.items():
            conf = float((out or {}).get("confidence", 0.3) or 0.3)
            if out and isinstance(out.get("selection"), list) and out["selection"]:
                # take the first id as the primary suggestion
                sid = str(out["selection"][0])
                selections.append(sid)
                sel_weights.append(conf)
            if out and isinstance(out.get("path_ids"), list) and out["path_ids"]:
                pids = [str(x) for x in out["path_ids"]]
                path_ids.append(pids)
                path_weights.append(conf)

        # Task-specific aggregation
        if task == "full_day_traj":
            if path_ids:
                best_idx = max(range(len(path_ids)), key=lambda i: path_weights[i])
                coords: List[List[float]] = [
                    id2coord[pid] for pid in path_ids[best_idx] if pid in id2coord
                ]
                if coords:
                    return {
                        "result": {"type": "path", "value": coords},
                        "confidence": path_weights[best_idx],
                        "details": {"per_agent": per_agent, "evidence_used": evid},
                    }
            return {
                "result": None,
                "confidence": 0.0,
                "details": {"per_agent": per_agent, "evidence_used": evid},
            }

        # next_position or future_position: choose id by weighted voting
        if not selections:
            return {
                "result": None,
                "confidence": 0.0,
                "details": {"per_agent": per_agent, "evidence_used": evid},
            }
        # vote
        from collections import defaultdict

        agg_scores: Dict[str, float] = defaultdict(float)
        for sid, w in zip(selections, sel_weights):
            agg_scores[sid] += w
        if not agg_scores:
            return {
                "result": None,
                "confidence": 0.0,
                "details": {"per_agent": per_agent, "evidence_used": evid},
            }
        best_id = max(agg_scores, key=lambda k: agg_scores[k])
        if best_id not in id2coord:
            return {
                "result": None,
                "confidence": float(agg_scores[best_id]),
                "details": {"per_agent": per_agent, "evidence_used": evid},
            }
        res_point = id2coord[best_id]
        return {
            "result": {"type": "point", "value": res_point},
            "confidence": float(agg_scores[best_id]),
            "details": {
                "per_agent": per_agent,
                "evidence_used": evid,
                "selected_id": best_id,
            },
        }

    def invoke(
        self, inputs: Dict[str, Any], config: Any | None = None
    ) -> Dict[str, Any]:
        logger = logging.getLogger("mrra.reflection")
        # 1) retrieve evidence
        # Prefer modern retriever.invoke(); keep legacy fallback for compatibility
        try:
            evidence = self.retriever.invoke(inputs)
        except Exception:
            evidence = self.retriever.get_relevant_documents(inputs)

        state: Dict[str, Any] = {"evidence": evidence, "history": []}
        logger.debug(
            f"orchestrator evidence count={len(evidence) if isinstance(evidence, list) else 'n/a'}"
        )
        # 2) reflection rounds
        for _ in range(int(self.max_round)):
            outs: Dict[str, Any] = {}
            for name, agent in self.subagents.items():
                # 不做兜底：若 LLM/子智能体错误（如无效密钥），直接抛出异常
                outs[name] = agent(self._compose_query(inputs, state))
                logger.debug(
                    f"orchestrator subagent[{name}] output keys={list(outs[name].keys()) if isinstance(outs[name], dict) else type(outs[name])}"
                )
            state["history"].append(outs)
        # 3) aggregate
        logger.debug("orchestrator aggregating results")
        return self._aggregate(state, task=inputs.get("task", "next_position"))
