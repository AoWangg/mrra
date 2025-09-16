from __future__ import annotations

import math
from typing import Tuple, List


EARTH_RADIUS_KM = 6371.0088


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometers."""
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def to_grid(lat: float, lon: float, grid_size_m: int = 200) -> Tuple[int, int]:
    """Rough equirectangular grid index; good enough for city-scale binning.

    grid_size_m: size in meters of grid cell edge.
    """
    # meters per degree approximation at equator
    m_per_deg_lat = 111_132
    m_per_deg_lon = 111_320 * math.cos(math.radians(lat))
    gy = int(math.floor(lat * m_per_deg_lat / grid_size_m))
    gx = int(math.floor(lon * m_per_deg_lon / grid_size_m))
    return gy, gx


def snap_to_grid(lat: float, lon: float, grid_size_m: int = 200) -> Tuple[float, float]:
    gy, gx = to_grid(lat, lon, grid_size_m)
    # convert back to approx lat/lon at cell center
    m_per_deg_lat = 111_132
    m_per_deg_lon = 111_320 * math.cos(math.radians(lat))
    lat_center = (gy + 0.5) * (grid_size_m / m_per_deg_lat)
    lon_center = (gx + 0.5) * (grid_size_m / m_per_deg_lon)
    return lat_center, lon_center


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    y = math.sin(math.radians(lon2 - lon1)) * math.cos(math.radians(lat2))
    x = math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) - (
        math.sin(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.cos(math.radians(lon2 - lon1))
    )
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def moving_average(
    points: List[Tuple[float, float]], window: int = 3
) -> List[Tuple[float, float]]:
    if window <= 1 or len(points) <= 2:
        return points
    res: List[Tuple[float, float]] = []
    for i in range(len(points)):
        left_idx = max(0, i - window + 1)
        chunk = points[left_idx : i + 1]
        lat = sum(p[0] for p in chunk) / len(chunk)
        lon = sum(p[1] for p in chunk) / len(chunk)
        res.append((lat, lon))
    return res
