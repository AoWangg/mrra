import os
import json
import logging
from datetime import datetime
from typing import List

import pandas as pd

from mrra.data.trajectory import TrajectoryBatch
from mrra.data.activity import ActivityExtractor
from mrra.graph.mobility_graph import MobilityGraph, GraphConfig
from mrra.analysis.activity_purpose import ActivityPurposeAssigner
from mrra.persist.cache import CacheManager, compute_tb_hash
from mrra.graph.pattern import PatternGenerate
from mrra.retriever.graph_rag import GraphRAGGenerate
from mrra.agents.builder import build_mrra_agent
from mrra.agents.subagents import make_llm


def load_geolife_plt(path: str, user_id: str) -> pd.DataFrame:
    """Parse a Geolife .plt file (WGS84) into a DataFrame with required columns.

    Skips the 6-line header. Columns per data line:
    lat, lon, 0, altitude(feet), timestamp_float, YYYY-MM-DD, HH:MM:SS
    """
    rows: List[dict] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if i < 6:
                continue
            parts = line.strip().split(",")
            if len(parts) < 7:
                continue
            try:
                lat = float(parts[0])
                lon = float(parts[1])
                # parts[4] is Excel date; prefer explicit date/time in [5],[6]
                dt = datetime.strptime(parts[5] + " " + parts[6], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            rows.append(
                {
                    "user_id": user_id,
                    "timestamp": dt.isoformat(),
                    "latitude": lat,
                    "longitude": lon,
                }
            )
    return pd.DataFrame(rows)


def list_geolife_users(base_dir: str) -> list[str]:
    users = []
    if not os.path.isdir(base_dir):
        return users
    for name in sorted(os.listdir(base_dir)):
        udir = os.path.join(base_dir, name)
        traj = os.path.join(udir, "Trajectory")
        if os.path.isdir(traj):
            users.append(name)
    return users


def load_geolife_user(base_dir: str, user_folder: str) -> pd.DataFrame:
    """Load all PLT files for one user into a single DataFrame."""
    traj_dir = os.path.join(base_dir, user_folder, "Trajectory")
    if not os.path.isdir(traj_dir):
        raise FileNotFoundError(f"Trajectory not found: {traj_dir}")
    frames: list[pd.DataFrame] = []
    for fname in sorted(os.listdir(traj_dir)):
        if not fname.lower().endswith(".plt"):
            continue
        fpath = os.path.join(traj_dir, fname)
        df = load_geolife_plt(fpath, user_id=f"geolife_{user_folder}")
        frames.append(df)
    if not frames:
        raise ValueError(f"No PLT files under {traj_dir}")
    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values("timestamp").reset_index(drop=True)
    return out


def main():
    # 载入 scripts/.env 中的配置与密钥
    def load_env_file(path: str) -> None:
        if not os.path.isfile(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" not in s:
                    continue
                k, v = s.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                os.environ[k] = v

    load_env_file(os.path.join("scripts", ".env"))

    api_key = (
        os.environ.get("MRRA_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or ""
    )
    provider = os.environ.get("MRRA_API_PROVIDER", "openai-compatible")
    model = os.environ.get("MRRA_API_MODEL", "qwen-plus")
    base_url = os.environ.get(
        "MRRA_API_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    try:
        temperature = float(os.environ.get("MRRA_API_TEMPERATURE", "0.2"))
    except Exception:
        temperature = 0.2

    llm_cfg = None
    llm_obj = None
    if api_key:
        llm_cfg = dict(
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
        )
        try:
            llm_obj = make_llm(**llm_cfg)
        except Exception:
            llm_obj = None
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    base_dir = os.path.join("scripts", "Data")
    # Choose target user folder
    target_user = os.environ.get("GEOLIFE_USER")
    users = list_geolife_users(base_dir)
    if not users:
        raise FileNotFoundError(f"No Geolife users found under {base_dir}")
    if target_user is None:
        target_user = users[0]
    elif target_user not in users:
        raise ValueError(
            f"GEOLIFE_USER={target_user} not found under {base_dir}. Available: {users[:10]}..."
        )

    df = load_geolife_user(base_dir, target_user)
    print(
        f"Loaded PLT rows: {len(df)} users: {df['user_id'].nunique()} user: {target_user}"
    )
    print("Preview:")
    print(df.head(8).to_string(index=False))

    tb = TrajectoryBatch(df)
    cm = CacheManager()
    tb_hash = compute_tb_hash(tb)

    # 提取活动并缓存
    ext_cfg = dict(
        method="radius",
        radius_m=300,
        min_dwell_minutes=30,
        max_gap_minutes=90,
        grid_size_m=200,
    )
    llm_flag = "1" if llm_obj else "0"
    acts_key = (
        f"r{ext_cfg['radius_m']}_min{ext_cfg['min_dwell_minutes']}"
        f"_gap{ext_cfg['max_gap_minutes']}_grid{ext_cfg['grid_size_m']}_llm{llm_flag}"
    )
    acts = cm.load_activities(tb_hash, acts_key)
    if acts is None:
        acts = ActivityExtractor(tb, **ext_cfg).extract()
        # 为每个活动赋予目的；若 llm_obj 可用将调用大模型细化，否则使用启发式（并发加速）
        acts = ActivityPurposeAssigner(tb, llm=llm_obj, concurrency=8).assign(acts)
        cm.save_activities(tb_hash, acts_key, acts)
    print(f"Extracted activities: {len(acts)} (first 5)")
    for a in acts[:5]:
        print(
            f" - {a.activity_type}/{a.purpose}@{a.place_id} {a.start}~{a.end} ({a.duration_min:.1f}m)"
        )
    # 生成并缓存“活动链”（按用户时间排序的相邻活动转移）
    chains_key = f"chains_{abs(hash(acts_key)) % (10**8)}"
    chains = cm.load_json(tb_hash, chains_key, kind="chains")
    if chains is None:
        from collections import defaultdict

        user_groups = defaultdict(list)
        for a in sorted(acts, key=lambda r: (r.user_id, r.start)):
            user_groups[a.user_id].append(a)
        chain_records = []
        for uid, seq in user_groups.items():
            for i in range(1, len(seq)):
                prev, cur = seq[i - 1], seq[i]
                chain_records.append(
                    {
                        "user_id": uid,
                        "from_place": prev.place_id,
                        "to_place": cur.place_id,
                        "from_purpose": getattr(prev, "purpose", "其他"),
                        "to_purpose": getattr(cur, "purpose", "其他"),
                        "at": str(cur.start),
                    }
                )
        chains = {"count": len(chain_records), "records": chain_records[:1000]}
        cm.save_json(tb_hash, chains_key, chains, kind="chains")

    print("-----------------graph 构建-----------------")
    # 构图时注入同一 LLM 的目的赋值器，确保图中也使用 LLM 赋值结果
    # 构图并缓存（复用上面的 llm 判定逻辑）
    graph_key = f"grid{200}_mindwell{5}_actskey{abs(hash(acts_key)) % (10**8)}"
    G_cached = cm.load_graph(tb_hash, graph_key)
    cfg = GraphConfig(grid_size_m=200, min_dwell_minutes=5, use_activities=True)
    # 先创建一个 MobilityGraph 实例（使用已赋目的的 activities，避免再次调用 LLM）
    mg = MobilityGraph(tb, cfg, activities=acts, assume_purposes_assigned=True)
    if G_cached is not None:
        # 用缓存图覆盖（避免重复构图的成本）
        mg.G = G_cached
    else:
        cm.save_graph(tb_hash, graph_key, mg.G)
    G = mg.G
    print(f"Graph summary: nodes={G.number_of_nodes()} edges={G.number_of_edges()}")
    type_counts = {}
    for n, d in G.nodes(data=True):
        t = d.get("type", "na")
        type_counts[t] = type_counts.get(t, 0) + 1
    print("Node types:", type_counts)
    print("Sample loc nodes (up to 5):")
    loc_nodes = [(n, d) for n, d in G.nodes(data=True) if d.get("type") == "loc"]
    for n, d in loc_nodes[:5]:
        print(" -", n, {k: d.get(k) for k in ("lat", "lon", "gy", "gx", "top_succ")})

    # Build retriever and agent，直接传入 MobilityGraph 实例
    retriever = GraphRAGGenerate(tb=tb, mobility_graph=mg)
    pat = PatternGenerate(tb)
    target_user_id = tb.users()[0]
    # 模式生成与缓存
    patterns_key = f"patterns_{target_user_id}"
    patterns = cm.load_json(tb_hash, patterns_key, kind="patterns")
    if patterns is None:
        patterns = pat.long_short_patterns(target_user_id)
        cm.save_json(tb_hash, patterns_key, patterns, kind="patterns")
    print("PatternGenerate for", target_user_id)
    print(json.dumps(patterns, ensure_ascii=False, indent=2))

    # LLM config from env for safety
    reflection_cfg = dict(
        max_round=1,
        subAgents=[
            {
                "name": "temporal",
                "prompt": "从 Options 中选择最可能的位置 id（selection），不要输出经纬度。",
            },
            {
                "name": "spatial",
                "prompt": "从 Options 中选择最可能的位置 id（selection），不要输出经纬度。",
            },
        ],
        aggregator="confidence_weighted_voting",
    )
    agent = None
    if llm_cfg is not None:
        agent = build_mrra_agent(
            llm=llm_cfg, retriever=retriever, reflection=reflection_cfg
        )

    # Build queries around last timestamp
    user_df = tb.for_user(target_user_id)
    last_ts = user_df.iloc[-1]["timestamp_local"].strftime("%Y-%m-%d %H:%M:%S")
    # 演示：以“用餐”目的作为种子做位置检索（若图中存在该目的）
    try:
        docs = retriever.get_relevant_documents(
            {"user_id": target_user_id, "t": last_ts, "purpose": "用餐", "k": 5}
        )
        if docs:
            print("Top locs seeded by purpose=用餐:")
            for d in docs:
                print(
                    " -", d.metadata.get("node"), f"score={d.metadata.get('score'):.4f}"
                )
    except Exception as _:
        pass
    if agent is not None:
        for task, extra in (
            ("next_position", {"t": last_ts}),
            ("future_position", {"t": last_ts}),
            (
                "full_day_traj",
                {"date": user_df.iloc[-1]["timestamp_local"].strftime("%Y-%m-%d")},
            ),
        ):
            payload = {"task": task, "user_id": target_user_id}
            payload.update(extra)
            try:
                res = agent.invoke(payload)
                print(f"MRRA {task} =>", json.dumps(res, ensure_ascii=False))
            except Exception as e:
                print(f"MRRA {task} failed:", repr(e))
    else:
        print("No API key in scripts/.env; skipped MRRA agent invocation.")


if __name__ == "__main__":
    main()
