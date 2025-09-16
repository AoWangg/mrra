from __future__ import annotations

import os
import json
import pickle
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Optional, List

import pandas as pd
import networkx as nx

from mrra.data.trajectory import TrajectoryBatch
from mrra.data.activity import ActivityExtractor, ActivityRecord


def compute_tb_hash(tb: TrajectoryBatch) -> str:
    """为 TrajectoryBatch 生成稳定哈希，区分不同数据输入。"""
    df = tb.df[["user_id", "timestamp", "latitude", "longitude"]].copy()
    # 为避免时区或精度差异，统一为字符串
    df["timestamp"] = df["timestamp"].astype(str)
    df["user_id"] = df["user_id"].astype(str)
    df["latitude"] = df["latitude"].astype(str)
    df["longitude"] = df["longitude"].astype(str)
    hv = pd.util.hash_pandas_object(df, index=False).values.tobytes()
    h = hashlib.sha1(hv).hexdigest()
    return h


@dataclass
class CacheManager:
    base_dir: str = ".mrra_cache"

    # ---------- 路径管理 ----------
    def _ensure_dir(self, *parts: str) -> str:
        path = os.path.join(*parts)
        os.makedirs(path, exist_ok=True)
        return path

    def _root(self, tb_hash: str) -> str:
        return self._ensure_dir(self.base_dir, tb_hash)

    def activities_path(self, tb_hash: str, key: str) -> str:
        return os.path.join(self._root(tb_hash), f"activities_{key}.json")

    def graph_path(self, tb_hash: str, key: str) -> str:
        return os.path.join(self._root(tb_hash), f"graph_{key}.gpickle")

    def patterns_path(self, tb_hash: str, key: str) -> str:
        return os.path.join(self._root(tb_hash), f"patterns_{key}.json")

    def chains_path(self, tb_hash: str, key: str) -> str:
        return os.path.join(self._root(tb_hash), f"chains_{key}.json")

    # ---------- 活动缓存 ----------
    def load_activities(self, tb_hash: str, key: str) -> Optional[List[ActivityRecord]]:
        path = self.activities_path(tb_hash, key)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            df = pd.DataFrame(data)
            return ActivityExtractor.from_dataframe(df)
        except Exception:
            return None

    def save_activities(
        self, tb_hash: str, key: str, records: List[ActivityRecord]
    ) -> str:
        path = self.activities_path(tb_hash, key)
        df = ActivityExtractor.to_dataframe(records)
        # 将时间列转为 ISO 字符串
        out = df.copy()
        out["start"] = out["start"].astype(str)
        out["end"] = out["end"].astype(str)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out.to_dict(orient="records"), f, ensure_ascii=False)
        return path

    # ---------- 图缓存 ----------
    def load_graph(self, tb_hash: str, key: str) -> Optional[nx.MultiDiGraph]:
        path = self.graph_path(tb_hash, key)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            return None

    def save_graph(self, tb_hash: str, key: str, G: nx.MultiDiGraph) -> str:
        path = self.graph_path(tb_hash, key)
        with open(path, "wb") as f:
            pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)
        return path

    # ---------- 模式/链缓存（JSON） ----------
    def load_json(self, tb_hash: str, key: str, kind: str) -> Optional[Dict[str, Any]]:
        if kind == "patterns":
            path = self.patterns_path(tb_hash, key)
        else:
            path = self.chains_path(tb_hash, key)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_json(self, tb_hash: str, key: str, obj: Dict[str, Any], kind: str) -> str:
        if kind == "patterns":
            path = self.patterns_path(tb_hash, key)
        else:
            path = self.chains_path(tb_hash, key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        return path
