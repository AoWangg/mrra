from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from mrra.data.trajectory import TrajectoryBatch
from mrra.data.activity import ActivityRecord


DEFAULT_PURPOSE_CATEGORIES: Tuple[str, ...] = (
    "居住",
    "工作",
    "上学",
    "用餐",
    "购物",
    "医疗",
    "娱乐",
    "锻炼",
    "社交",
    "接送",
    "旅游",
    "通勤中转",
    "其他",
)


@dataclass
class ActivityPurposeAssigner:
    """为活动分配“活动目的”。

    支持两种方式：
    - 规则启发式（默认，无外部依赖，稳定可用）
    - 大模型分类（可选，需在构造时提供 llm 客户端；失败则回退到规则）

    llm 客户端应兼容 LangChain 的 ChatModel 接口（例如 langchain-openai.ChatOpenAI）。
    只要实现 .invoke 或 __call__ 接口，传入字符串或消息即可返回文本；本模块会尝试解析 JSON。
    """

    tb: TrajectoryBatch
    categories: Tuple[str, ...] = DEFAULT_PURPOSE_CATEGORIES
    llm: Optional[Any] = None
    concurrency: int = 8  # 大模型推断的并发数
    llm_timeout: Optional[float] = 60.0

    def assign(self, activities: Iterable[ActivityRecord]) -> List[ActivityRecord]:
        acts = list(activities)
        if not acts:
            return acts

        # 为启发式准备场所粒度统计
        place_stats = self._aggregate_place_stats(acts)

        # 先全部给出启发式结果
        heuristics: List[str] = []
        for ar in acts:
            heuristics.append(self._heuristic_purpose(ar, place_stats.get(ar.place_id)))

        # 若有 LLM，采用并发细化；无 LLM 则直接落地启发式
        if self.llm is not None and self.concurrency > 1:

            def _worker(
                idx_ar: Tuple[int, ActivityRecord],
            ) -> Tuple[int, Optional[str]]:
                idx, act = idx_ar
                try:
                    return idx, self._llm_purpose(
                        act, place_stats.get(act.place_id), draft=heuristics[idx]
                    )
                except Exception:
                    return idx, None

            max_workers = max(1, min(int(self.concurrency), len(acts)))
            with ThreadPoolExecutor(max_workers=max_workers) as ex:
                futures = [ex.submit(_worker, (i, ar)) for i, ar in enumerate(acts)]
                for fut in as_completed(futures):
                    try:
                        idx, pv = fut.result(
                            timeout=self.llm_timeout if self.llm_timeout else None
                        )
                        if pv:
                            heuristics[idx] = pv
                    except Exception:
                        # 超时或其他错误，保持启发式
                        pass

        elif self.llm is not None:
            # 单线程调用 LLM（保底）
            for i, ar in enumerate(acts):
                try:
                    pv = self._llm_purpose(
                        ar, place_stats.get(ar.place_id), draft=heuristics[i]
                    )
                    if pv:
                        heuristics[i] = pv
                except Exception:
                    pass

        # 写回结果
        for ar, pv in zip(acts, heuristics):
            ar.purpose = pv or "其他"
        return acts

    # ------------------------
    # Aggregations
    # ------------------------
    def _aggregate_place_stats(
        self, acts: List[ActivityRecord]
    ) -> Dict[str, Dict[str, Any]]:
        stats: Dict[str, Dict[str, Any]] = {}
        for ar in acts:
            s = stats.setdefault(
                ar.place_id,
                {
                    "total_duration": 0.0,
                    "visits": 0,
                    "hours": {h: 0.0 for h in range(24)},
                    "dows": {d: 0.0 for d in range(7)},
                },
            )
            s["total_duration"] += float(ar.duration_min)
            s["visits"] += 1
            h = int(ar.start.hour)
            d = int(ar.start.dayofweek)
            s["hours"][h] = s["hours"].get(h, 0.0) + float(ar.duration_min)
            s["dows"][d] = s["dows"].get(d, 0.0) + float(ar.duration_min)
        return stats

    # ------------------------
    # Heuristics
    # ------------------------
    def _heuristic_purpose(
        self, ar: ActivityRecord, s: Optional[Dict[str, Any]]
    ) -> str:
        dur = float(ar.duration_min)
        h = int(ar.start.hour)
        dow = int(ar.start.dayofweek)
        t = (h + (ar.end.hour - ar.start.hour) / 2.0) % 24  # 粗略活动时间段中心

        # 已有的活动类型可作为强特征
        if ar.activity_type == "home":
            return "居住"
        if ar.activity_type == "work":
            return "工作"

        # 夜晚较长停留（22:00-6:00，>=120m）
        if dur >= 120 and (h >= 22 or h <= 6):
            return "居住"

        # 工作日白天较长停留（>=180m）
        if dur >= 180 and dow in (0, 1, 2, 3, 4) and 8 <= h <= 19:
            return "工作"

        # 就餐：11:00-14:00 或 17:30-20:30，停留 15-120 分钟
        if 11 <= t <= 14 or 17.5 <= t <= 20.5:
            if 15 <= dur <= 120:
                return "用餐"

        # 购物/娱乐：周末或晚间，停留 30-240 分钟
        if (dow in (5, 6) or 18 <= t <= 22) and 30 <= dur <= 240:
            return "购物" if t <= 20 else "娱乐"

        # 医疗：工作日白天短中停留（20-120 分钟）且不频繁（场所访问次数低）
        if (
            s is not None
            and s.get("visits", 0) <= 2
            and dow in (0, 1, 2, 3, 4)
            and 9 <= h <= 17
            and 20 <= dur <= 120
        ):
            return "医疗"

        # 锻炼：清晨/傍晚 30-120 分钟
        if (6 <= t <= 8 or 18 <= t <= 21) and 30 <= dur <= 120:
            return "锻炼"

        # 社交：晚间 60-240 分钟
        if 19 <= t <= 23 and 60 <= dur <= 240:
            return "社交"

        # 通勤中转：很短的停留（<=15 分钟）
        if dur <= 15:
            return "通勤中转"

        return "其他"

    # ------------------------
    # LLM
    # ------------------------
    def _llm_purpose(
        self, ar: ActivityRecord, s: Optional[Dict[str, Any]], draft: Optional[str]
    ) -> Optional[str]:
        """使用 LLM 进行细化分类。输入中文提示，要求从限定类别中选择并返回 JSON。"""
        llm = self.llm
        if llm is None:
            return None

        categories = ",".join(self.categories)
        place_json = {
            "user_id": ar.user_id,
            "place_id": ar.place_id,
            "lat": round(float(ar.latitude), 6),
            "lon": round(float(ar.longitude), 6),
            "start": str(pd.to_datetime(ar.start)),
            "end": str(pd.to_datetime(ar.end)),
            "duration_min": round(float(ar.duration_min), 2),
            "hour": int(ar.start.hour),
            "dow": int(ar.start.dayofweek),
            "activity_type": ar.activity_type,
        }
        if s is not None:
            place_json["stats"] = {
                "total_duration": round(float(s.get("total_duration", 0.0)), 1),
                "visits": int(s.get("visits", 0)),
            }

        system = "你是出行行为分析助手。只返回一个 JSON 对象，无其它文本。"
        human = (
            "请根据以下活动信息，判定其‘活动目的’：\n"
            f"允许的类别：{categories}\n"
            "尽量从这些类别中二选一或一选一，无法判断用‘其他’。\n"
            '返回 JSON：{"purpose":类别,"confidence":0-1,"reason":中文简述}。\n'
            f"活动：{place_json}\n"
            f"若你倾向于：{draft or '未知'}，可在不确定时参考。"
        )

        # 兼容 LangChain ChatModel 或简单 __call__ 接口
        try:
            if hasattr(llm, "invoke"):
                # 优先按 LangChain ChatModel 走消息列表；失败则退化为直接传字符串
                try:
                    from langchain_core.messages import SystemMessage, HumanMessage  # type: ignore

                    messages = [
                        SystemMessage(content=system),
                        HumanMessage(content=human),
                    ]
                    msg = llm.invoke(messages)
                except Exception:
                    msg = llm.invoke(human)
                content = getattr(msg, "content", msg)
            else:
                content = llm(human)
            if not isinstance(content, str):
                content = str(content)
        except Exception:
            return None

        import json
        import re

        m = re.search(r"\{[\s\S]*\}", content)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
            cand = obj.get("purpose")
            if isinstance(cand, str) and cand in self.categories:
                return cand
        except Exception:
            return None
        return None
