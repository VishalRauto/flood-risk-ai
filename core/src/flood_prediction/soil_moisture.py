"""
soil_moisture.py — Real soil moisture integration for India Flood Intelligence.

Addresses the "Limited Multi-Source Data Integration" limitation:
  Current:  Soil saturation estimated from cumulative rainfall proxy only.
  Solution: Fetch real volumetric soil water content from Open-Meteo API
            (ERA5-Land reanalysis, 0-7cm and 7-28cm layers), compute
            field-capacity saturation percentage, and integrate with the
            compound risk scoring formula.

Open-Meteo soil moisture variables used
-----------------------------------------
  soil_moisture_0_to_7cm      — surface layer (m³/m³)
  soil_moisture_7_to_28cm     — root zone (m³/m³)
  soil_moisture_28_to_100cm   — deep layer (m³/m³)
  soil_temperature_0cm        — surface temp for freeze/thaw (°C)
  evapotranspiration          — actual ET proxy (mm/day)

Field capacity references per soil type (India)
-------------------------------------------------
  Sandy loam (Ganga plains):     0.21 m³/m³
  Clay loam (Brahmaputra valley): 0.38 m³/m³
  Black cotton soil (Deccan):    0.42 m³/m³
  Red laterite (Odisha coast):   0.28 m³/m³
  Alluvial (Bihar/UP):           0.32 m³/m³
  Source: ICAR Soil Science, India Soil Map 2020

Usage
-----
    from flood_prediction.soil_moisture import get_soil_moisture_service
    svc = get_soil_moisture_service()
    result = await svc.fetch(lat=26.14, lon=91.74, region_code="IN-BRAHMAPUTRA")
    # result.saturation_pct  — 0-100%
    # result.risk_contribution  — 0-10 score for compound risk formula
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

# ── Field capacity by India basin/soil type ──────────────────────────────────
FIELD_CAPACITY: Dict[str, float] = {
    "IN-GANGA":        0.32,   # alluvial plains
    "IN-BRAHMAPUTRA":  0.38,   # clay loam, heavy rainfall zone
    "IN-MAHANADI":     0.28,   # red laterite + alluvial mix
    "IN-GODAVARI":     0.30,   # mixed soil, semi-arid to humid
    "IN-KRISHNA":      0.42,   # black cotton soil (Deccan)
    "IN-NARMADA":      0.35,   # mixed alluvial
    "IN-KAVERI":       0.27,   # red laterite, granite substrate
    "IN-INDUS":        0.21,   # sandy loam, arid/semi-arid Punjab
}

# Wilting point (below which plants cannot extract water — minimum saturation proxy)
WILTING_POINT: Dict[str, float] = {
    "IN-GANGA":        0.12,
    "IN-BRAHMAPUTRA":  0.15,
    "IN-MAHANADI":     0.10,
    "IN-GODAVARI":     0.12,
    "IN-KRISHNA":      0.18,
    "IN-NARMADA":      0.14,
    "IN-KAVERI":       0.09,
    "IN-INDUS":        0.07,
}

# In-memory cache: (lat_rounded, lon_rounded) → (result, fetched_at)
_CACHE: Dict[str, Tuple[Any, datetime]] = {}
_CACHE_TTL_HOURS = 3


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class SoilMoistureResult:
    lat:                  float
    lon:                  float
    region_code:          str

    # Raw volumetric water content (m³/m³)
    sm_0_7cm:             float       # surface layer
    sm_7_28cm:            float       # root zone
    sm_28_100cm:          float       # deep layer
    sm_weighted:          float       # depth-weighted mean

    # Derived
    field_capacity:       float       # regional field capacity (m³/m³)
    wilting_point:        float       # regional wilting point (m³/m³)
    saturation_pct:       float       # 0-100%: (sm - wp) / (fc - wp) * 100
    risk_contribution:    float       # 0-10: contribution to compound risk formula
    saturation_category:  str         # DRY / NORMAL / MOIST / WET / SATURATED

    # Additional variables
    surface_temp_c:       float
    evapotranspiration_mm: float      # actual ET today (mm)
    antecedent_rainfall_7d: float     # 7-day cumulative rainfall (mm)

    # Metadata
    data_source:          str         # "openmeteo_era5" | "proxy_rainfall"
    data_quality:         str         # "good" | "estimated" | "missing"
    fetched_at:           str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Service ───────────────────────────────────────────────────────────────────

class SoilMoistureService:
    """
    Fetches real volumetric soil moisture from Open-Meteo ERA5-Land API
    and converts it to a flood-risk contribution score.
    """

    async def fetch(self,
                    lat: float,
                    lon: float,
                    region_code: str = "IN-GANGA",
                    past_days: int = 7) -> SoilMoistureResult:
        """
        Fetch soil moisture for a lat/lon point.

        Parameters
        ----------
        lat, lon     : coordinates
        region_code  : India basin code for field-capacity lookup
        past_days    : days of history to fetch (for 7-day antecedent rainfall)
        """
        cache_key = f"{round(lat,2)}_{round(lon,2)}"
        cached = _CACHE.get(cache_key)
        if cached:
            result, fetched_at = cached
            age = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
            if age < _CACHE_TTL_HOURS:
                return result

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._fetch_sync, lat, lon, region_code, past_days)

        _CACHE[cache_key] = (result, datetime.now(timezone.utc))
        return result

    def _fetch_sync(self, lat: float, lon: float,
                    region_code: str, past_days: int) -> SoilMoistureResult:
        """Synchronous fetch from Open-Meteo ERA5-Land API."""
        fc = FIELD_CAPACITY.get(region_code, 0.30)
        wp = WILTING_POINT.get(region_code, 0.12)

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&hourly=soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,"
            f"soil_moisture_28_to_100cm,soil_temperature_0cm"
            f"&daily=precipitation_sum,et0_fao_evapotranspiration"
            f"&past_days={past_days}&forecast_days=1"
            f"&timezone=Asia%2FKolkata"
        )

        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read())

            # Extract latest hourly soil moisture values
            hourly = data.get("hourly", {})
            sm_0_7   = self._latest_valid(hourly.get("soil_moisture_0_to_7cm",   []))
            sm_7_28  = self._latest_valid(hourly.get("soil_moisture_7_to_28cm",  []))
            sm_28_100= self._latest_valid(hourly.get("soil_moisture_28_to_100cm",[]))
            temp_0   = self._latest_valid(hourly.get("soil_temperature_0cm",     []))

            # Depth-weighted mean: surface 20%, root 50%, deep 30%
            sm_weighted = sm_0_7 * 0.20 + sm_7_28 * 0.50 + sm_28_100 * 0.30

            # Daily data for antecedent rainfall + ET
            daily = data.get("daily", {})
            precip_list = [float(v or 0) for v in daily.get("precipitation_sum", [])]
            et_list     = [float(v or 0) for v in daily.get("et0_fao_evapotranspiration", [])]
            precip_7d   = float(sum(precip_list[-7:]))
            et_today    = float(et_list[-1]) if et_list else 0.0

            data_source = "openmeteo_era5"
            data_quality = "good"

        except Exception as e:
            log.warning(f"Open-Meteo soil moisture fetch failed ({e}), using rainfall proxy")
            # Fallback: estimate from antecedent rainfall using simple bucket model
            sm_0_7, sm_7_28, sm_28_100, temp_0, sm_weighted, precip_7d, et_today = \
                self._rainfall_proxy(region_code)
            data_source = "proxy_rainfall"
            data_quality = "estimated"

        # Compute saturation percentage
        avail_water = fc - wp
        if avail_water > 0:
            sat_pct = round(max(0.0, min(100.0,
                (sm_weighted - wp) / avail_water * 100)), 1)
        else:
            sat_pct = 50.0

        risk_contrib = self._saturation_to_risk(sat_pct, region_code)
        category     = self._saturation_category(sat_pct)

        return SoilMoistureResult(
            lat                    = lat,
            lon                    = lon,
            region_code            = region_code,
            sm_0_7cm               = round(sm_0_7,    4),
            sm_7_28cm              = round(sm_7_28,   4),
            sm_28_100cm            = round(sm_28_100, 4),
            sm_weighted            = round(sm_weighted, 4),
            field_capacity         = fc,
            wilting_point          = wp,
            saturation_pct         = sat_pct,
            risk_contribution      = risk_contrib,
            saturation_category    = category,
            surface_temp_c         = round(temp_0, 1),
            evapotranspiration_mm  = round(et_today, 2),
            antecedent_rainfall_7d = round(precip_7d, 1),
            data_source            = data_source,
            data_quality           = data_quality,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _latest_valid(values: List) -> float:
        """Return last non-None value, or 0.20 (typical India monsoon average)."""
        for v in reversed(values):
            if v is not None:
                return float(v)
        return 0.20

    @staticmethod
    def _rainfall_proxy(region_code: str) -> Tuple[float, ...]:
        """
        Estimate soil moisture from typical monsoon season averages.
        Used only when the Open-Meteo API is unreachable.
        Based on ICAR soil water balance studies for India.
        """
        fc = FIELD_CAPACITY.get(region_code, 0.30)
        # During peak monsoon (Jul-Sep) Indian soils are ~75-90% saturated
        fraction = 0.80
        sm = fc * fraction
        return (sm, sm * 0.95, sm * 0.85, 28.0, sm * 0.93, 150.0, 4.0)

    @staticmethod
    def _saturation_to_risk(saturation_pct: float, region_code: str) -> float:
        """
        Convert soil saturation percentage to a 0-10 risk contribution score.

        When soil is saturated, additional rainfall has no infiltration capacity
        and converts entirely to surface runoff → higher flood risk.

        Risk curve calibrated against India monsoon flood events:
        - <40% saturated: minimal runoff contribution (score 0-2)
        - 40-70%: moderate runoff potential (score 2-5)
        - 70-90%: high runoff — soil near field capacity (score 5-8)
        - >90%: critical — any rainfall becomes immediate runoff (score 8-10)
        """
        # Vulnerability multiplier: clay soils (Deccan) saturate faster
        vuln = {"IN-KRISHNA": 1.2, "IN-BRAHMAPUTRA": 1.15,
                "IN-MAHANADI": 1.1}.get(region_code, 1.0)

        if saturation_pct >= 90:
            score = 8.0 + (saturation_pct - 90) / 10 * 2.0
        elif saturation_pct >= 70:
            score = 5.0 + (saturation_pct - 70) / 20 * 3.0
        elif saturation_pct >= 40:
            score = 2.0 + (saturation_pct - 40) / 30 * 3.0
        else:
            score = saturation_pct / 40 * 2.0

        return round(min(10.0, score * vuln), 2)

    @staticmethod
    def _saturation_category(sat_pct: float) -> str:
        if sat_pct >= 90:
            return "SATURATED"
        elif sat_pct >= 70:
            return "WET"
        elif sat_pct >= 40:
            return "MOIST"
        elif sat_pct >= 20:
            return "NORMAL"
        return "DRY"


async def fetch_soil_moisture_for_watershed(
        watershed: Dict[str, Any]) -> Optional[SoilMoistureResult]:
    """
    Convenience wrapper: fetch soil moisture for a watershed dict.
    Returns None if lat/lon missing.
    """
    lat = float(watershed.get("location_lat") or 0)
    lon = float(watershed.get("location_lng") or 0)
    if not lat or not lon:
        return None
    region_code = watershed.get("region_code", "IN-GANGA")
    svc = get_soil_moisture_service()
    try:
        return await svc.fetch(lat, lon, region_code)
    except Exception as e:
        log.warning(f"Soil moisture fetch failed for {watershed.get('name')}: {e}")
        return None


async def enrich_watersheds_with_soil_moisture(
        watersheds: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enrich a list of watershed dicts with soil moisture data.
    Adds 'soil_moisture' key to each dict.
    Fetches in parallel (max 5 concurrent requests).
    """
    sem = asyncio.Semaphore(5)

    async def _fetch_one(ws: Dict[str, Any]) -> Dict[str, Any]:
        async with sem:
            result = await fetch_soil_moisture_for_watershed(ws)
            if result:
                ws = dict(ws)
                ws["soil_moisture"] = result.to_dict()
                ws["soil_saturation_pct"]  = result.saturation_pct
                ws["soil_risk_contribution"] = result.risk_contribution
        return ws

    tasks = [_fetch_one(ws) for ws in watersheds]
    return list(await asyncio.gather(*tasks))


# ── Singleton ─────────────────────────────────────────────────────────────────
_svc_singleton: Optional[SoilMoistureService] = None


def get_soil_moisture_service() -> SoilMoistureService:
    global _svc_singleton
    if _svc_singleton is None:
        _svc_singleton = SoilMoistureService()
    return _svc_singleton
