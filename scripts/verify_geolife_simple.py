#!/usr/bin/env python3
"""
Simple Geolife verification script without caching.
Demonstrates basic MRRA functionality with minimal complexity.
"""

import os
import logging
from datetime import datetime
from typing import List

import pandas as pd

from mrra.data.trajectory import TrajectoryBatch
from mrra.data.activity import ActivityExtractor
from mrra.graph.mobility_graph import MobilityGraph, GraphConfig


def load_geolife_plt(path: str, user_id: str) -> pd.DataFrame:
    """Parse a Geolife .plt file into DataFrame with required columns."""
    rows: List[dict] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if i < 6:  # Skip 6-line header
                continue
            parts = line.strip().split(",")
            if len(parts) < 7:
                continue
            try:
                lat = float(parts[0])
                lon = float(parts[1])
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
    return out.sort_values("timestamp").reset_index(drop=True)


def list_geolife_users(base_dir: str) -> list[str]:
    """List available Geolife users."""
    users = []
    if not os.path.isdir(base_dir):
        return users
    for name in sorted(os.listdir(base_dir)):
        udir = os.path.join(base_dir, name)
        traj = os.path.join(udir, "Trajectory")
        if os.path.isdir(traj):
            users.append(name)
    return users


def main():
    """Simple verification of MRRA components with Geolife data."""
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )

    # Find Geolife data
    base_dir = os.path.join("scripts", "Data")
    users = list_geolife_users(base_dir)

    if not users:
        print(f"❌ No Geolife users found under {base_dir}")
        print(f"Please ensure Geolife dataset is available at {base_dir}")
        return

    # Use first available user
    target_user = users[0]
    print(f"📍 Using Geolife user: {target_user}")

    # Load trajectory data
    try:
        df = load_geolife_user(base_dir, target_user)
        print(f"✅ Loaded {len(df)} trajectory points for user {target_user}")
        print(f"📊 Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    except Exception as e:
        print(f"❌ Failed to load trajectory data: {e}")
        return

    # Create TrajectoryBatch
    try:
        tb = TrajectoryBatch(df)
        print(f"✅ Created TrajectoryBatch with {len(tb.users())} users")
        print(f"📈 Total trajectory points: {len(tb.df)}")
    except Exception as e:
        print(f"❌ Failed to create TrajectoryBatch: {e}")
        return

    # Extract activities (no caching)
    try:
        ext_cfg = {
            "method": "radius",
            "radius_m": 300,
            "min_dwell_minutes": 30,
            "max_gap_minutes": 90,
        }
        extractor = ActivityExtractor(tb, **ext_cfg)
        activities = extractor.extract()
        print(f"✅ Extracted {len(activities)} activities")

        # Show sample activities
        if activities:
            print("📋 Sample activities:")
            for i, act in enumerate(activities[:3]):
                print(
                    f"   {i + 1}. {act.activity_type} at place_{act.place_id} "
                    f"({act.duration_min:.1f} min)"
                )
    except Exception as e:
        print(f"❌ Failed to extract activities: {e}")
        return

    # Build mobility graph (no caching)
    try:
        cfg = GraphConfig(grid_size_m=200, min_dwell_minutes=5, use_activities=True)
        mg = MobilityGraph(tb, cfg, activities=activities)
        G = mg.G

        print("✅ Built mobility graph")
        print(f"📊 Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        # Show node type distribution
        type_counts = {}
        for _, d in G.nodes(data=True):
            node_type = d.get("type", "unknown")
            type_counts[node_type] = type_counts.get(node_type, 0) + 1

        print("📈 Node types:", type_counts)

    except Exception as e:
        print(f"❌ Failed to build mobility graph: {e}")
        return

    print("\n🎉 MRRA verification completed successfully!")
    print(
        "📝 All core components (TrajectoryBatch, ActivityExtractor, MobilityGraph) are working."
    )


if __name__ == "__main__":
    main()
