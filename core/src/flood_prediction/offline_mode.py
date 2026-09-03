"""
offline_mode.py — Resilient offline/degraded mode for India Flood Intelligence.

Addresses the "Real-Time Data Dependency" and "Connectivity" limitations:
  Current:  API outages interrupt prediction entirely.
  Solution: Multi-tier cache with TTL tracking, automatic mode detection,
            last-known-good data serving, retry-with-backoff, and a
            DataSourceManager that transparently falls back through:
              ONLINE → DEGRADED → CACHED → OFFLINE

Mode definitions
-----------------
  ONLINE    All primary APIs reachable, data fresh (< 2h)
  DEGRADED  Some APIs down OR data stale (2-6h); uses mix of live + cached
  CACHED    All APIs unreachable; serving last-known-good data (6-24h old)
  OFFLINE   No data at all; rule-based predictions only, no sensor data

Usage
-----
    from flood_prediction.offline_mode import get_data_manager
    mgr = get_data_manager()
    result = await mgr.get_watersheds_resilient(db_path)
    log.info(f"Mode: {mgr.current_mode}")  # "ONLINE" | "DEGRADED" | "CACHED" | "OFFLINE"
"""
from __future__ import annotations

import asyncio
import json
import logging
import pickle
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

log = logging.getLogger(__name__)

T = TypeVar("T")

# ── Cache TTLs ────────────────────────────────────────────────────────────────
TTL_ONLINE_SECONDS   = 3_600   # 1 hour — force re-fetch
TTL_DEGRADED_SECONDS = 21_600  # 6 hours — use cached but warn
TTL_STALE_SECONDS    = 86_400  # 24 hours — max age before OFFLINE mode

# ── Retry policy ──────────────────────────────────────────────────────────────
RETRY_DELAYS = [5, 15, 60]   # seconds between retry attempts
MAX_RETRIES  = 3


class OperationMode(str, Enum):
    ONLINE   = "ONLINE"
    DEGRADED = "DEGRADED"
    CACHED   = "CACHED"
    OFFLINE  = "OFFLINE"


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class CacheEntry:
    key:        str
    data:       Any
    fetched_at: float   # Unix timestamp
    source:     str     # "api" | "db" | "synthetic"

    @property
    def age_seconds(self) -> float:
        return time.time() - self.fetched_at

    @property
    def age_hours(self) -> float:
        return self.age_seconds / 3600

    def is_fresh(self) -> bool:
        return self.age_seconds < TTL_ONLINE_SECONDS

    def is_usable(self) -> bool:
        return self.age_seconds < TTL_STALE_SECONDS


@dataclass
class DataSourceStatus:
    name:          str
    reachable:     bool
    last_success:  Optional[float]  # Unix timestamp
    last_error:    Optional[str]
    latency_ms:    Optional[float]
    mode_contrib:  str              # what this source contributes to mode determination


@dataclass
class SystemModeReport:
    current_mode:  str
    sources:       List[DataSourceStatus]
    cache_entries: int
    oldest_cache_h: float
    message:       str
    recommendations: List[str]
    generated_at:  str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Persistent disk cache ─────────────────────────────────────────────────────

class DiskCache:
    """
    Simple pickle-based disk cache for last-known-good API responses.
    Used to survive container restarts.
    """

    def __init__(self, cache_dir: str = "/tmp/flood_offline_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace(":", "_")
        return self.cache_dir / f"{safe}.pkl"

    def get(self, key: str) -> Optional[CacheEntry]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            with open(p, "rb") as f:
                entry = pickle.load(f)
            if not entry.is_usable():
                p.unlink(missing_ok=True)
                return None
            return entry
        except Exception:
            return None

    def set(self, key: str, data: Any, source: str = "api") -> CacheEntry:
        entry = CacheEntry(key=key, data=data,
                           fetched_at=time.time(), source=source)
        p = self._path(key)
        try:
            with open(p, "wb") as f:
                pickle.dump(entry, f)
        except Exception as e:
            log.warning(f"DiskCache write failed for {key}: {e}")
        return entry

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def list_entries(self) -> List[Tuple[str, float]]:
        """Returns list of (key, age_hours) for all valid entries."""
        result = []
        for p in self.cache_dir.glob("*.pkl"):
            try:
                with open(p, "rb") as f:
                    entry = pickle.load(f)
                if entry.is_usable():
                    result.append((entry.key, entry.age_hours))
            except Exception:
                pass
        return result


# ── In-memory L1 cache ────────────────────────────────────────────────────────

class MemoryCache:
    def __init__(self):
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[CacheEntry]:
        entry = self._store.get(key)
        if entry and not entry.is_usable():
            del self._store[key]
            return None
        return entry

    def set(self, key: str, data: Any, source: str = "api") -> CacheEntry:
        entry = CacheEntry(key=key, data=data,
                           fetched_at=time.time(), source=source)
        self._store[key] = entry
        return entry

    def size(self) -> int:
        return len(self._store)


# ── Retry wrapper ─────────────────────────────────────────────────────────────

async def with_retry(fn: Callable, *args,
                     retries: int = MAX_RETRIES,
                     delays: List[int] = None,
                     fallback=None, **kwargs):
    """
    Run an async callable with exponential-ish retry.
    Returns fallback value if all attempts fail.
    """
    delays = delays or RETRY_DELAYS
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < retries:
                delay = delays[min(attempt, len(delays) - 1)]
                log.warning(f"Attempt {attempt+1}/{retries+1} failed ({e}), "
                            f"retrying in {delay}s...")
                await asyncio.sleep(delay)
    log.error(f"All {retries+1} attempts failed. Last error: {last_exc}")
    return fallback


# ── API health checker ────────────────────────────────────────────────────────

async def check_api_health() -> Dict[str, DataSourceStatus]:
    """Check reachability of all external APIs used by the system."""
    import urllib.request

    APIS = {
        "glofas_flood": "https://flood-api.open-meteo.com/v1/flood?latitude=26.14&longitude=91.74&daily=river_discharge&forecast_days=1",
        "openmeteo_weather": "https://api.open-meteo.com/v1/forecast?latitude=26.14&longitude=91.74&current=precipitation&forecast_days=1",
        "openmeteo_soil": "https://api.open-meteo.com/v1/forecast?latitude=26.14&longitude=91.74&hourly=soil_moisture_0_to_7cm&forecast_days=1",
    }

    statuses: Dict[str, DataSourceStatus] = {}

    for name, url in APIS.items():
        t0 = time.time()
        try:
            loop = asyncio.get_event_loop()
            def _get(u):
                with urllib.request.urlopen(u, timeout=8) as r:
                    return r.read()
            await loop.run_in_executor(None, _get, url)
            latency = round((time.time() - t0) * 1000, 1)
            statuses[name] = DataSourceStatus(
                name=name, reachable=True,
                last_success=time.time(), last_error=None,
                latency_ms=latency, mode_contrib="primary data source")
        except Exception as e:
            statuses[name] = DataSourceStatus(
                name=name, reachable=False,
                last_success=None, last_error=str(e)[:120],
                latency_ms=None, mode_contrib="unavailable — using cache")

    return statuses


def determine_mode(statuses: Dict[str, DataSourceStatus],
                   cache: MemoryCache,
                   disk_cache: DiskCache) -> OperationMode:
    """Determine current operation mode from API health + cache state."""
    reachable = [s for s in statuses.values() if s.reachable]
    total     = len(statuses)

    if len(reachable) == total:
        return OperationMode.ONLINE
    elif len(reachable) >= total // 2:
        return OperationMode.DEGRADED
    elif disk_cache.list_entries():
        return OperationMode.CACHED
    else:
        return OperationMode.OFFLINE


# ── Main DataSourceManager ────────────────────────────────────────────────────

class DataSourceManager:
    """
    Transparent data source manager with automatic offline fallback.

    All data access should go through this manager rather than calling
    Open-Meteo APIs directly, so the system remains operational during
    API outages.
    """

    def __init__(self, cache_dir: str = "/tmp/flood_offline_cache"):
        self._mem   = MemoryCache()
        self._disk  = DiskCache(cache_dir)
        self._mode  = OperationMode.ONLINE
        self._source_statuses: Dict[str, DataSourceStatus] = {}
        self._last_health_check = 0.0
        self._health_check_interval = 300  # seconds

    @property
    def current_mode(self) -> str:
        return self._mode.value

    # ── Health check ──────────────────────────────────────────────────────────

    async def refresh_health(self, force: bool = False) -> None:
        """Refresh API health status (throttled to every 5 min)."""
        now = time.time()
        if not force and (now - self._last_health_check) < self._health_check_interval:
            return
        try:
            self._source_statuses = await check_api_health()
            self._mode = determine_mode(
                self._source_statuses, self._mem, self._disk)
            self._last_health_check = now
            log.info(f"System mode: {self._mode.value} "
                     f"({sum(1 for s in self._source_statuses.values() if s.reachable)}"
                     f"/{len(self._source_statuses)} APIs reachable)")
        except Exception as e:
            log.warning(f"Health check failed: {e}")

    # ── Resilient data fetchers ───────────────────────────────────────────────

    async def get_watersheds_resilient(self, db_path: str) -> List[Dict[str, Any]]:
        """
        Get watersheds with full offline fallback chain:
          1. DB (always available)
          2. Memory cache (if DB fails)
          3. Disk cache (if memory empty)
        """
        cache_key = "watersheds_all"

        # Always try DB first (SQLite is local, no network needed)
        try:
            from . import db as _db
            watersheds = _db.get_watersheds(db_path)
            if watersheds:
                self._mem.set(cache_key, watersheds, source="db")
                self._disk.set(cache_key, watersheds, source="db")
                return watersheds
        except Exception as e:
            log.warning(f"DB watershed fetch failed: {e}")

        # L1 memory cache
        entry = self._mem.get(cache_key)
        if entry:
            log.info(f"Serving watersheds from memory cache "
                     f"(age {entry.age_hours:.1f}h)")
            return entry.data

        # L2 disk cache
        entry = self._disk.get(cache_key)
        if entry:
            log.info(f"Serving watersheds from disk cache "
                     f"(age {entry.age_hours:.1f}h)")
            self._mem.set(cache_key, entry.data, source="disk_cache")
            return entry.data

        log.error("No watershed data available from any source")
        return []

    async def fetch_glofas_resilient(self, lat: float, lon: float,
                                      site_code: str,
                                      past_days: int = 7) -> Optional[Dict]:
        """
        Fetch GloFAS discharge with retry + cache fallback.
        """
        cache_key = f"glofas_{site_code}_{past_days}d"

        # Check cache freshness
        mem_entry = self._mem.get(cache_key)
        if mem_entry and mem_entry.is_fresh():
            return mem_entry.data

        # Try live fetch with retry
        async def _live_fetch():
            url = (f"https://flood-api.open-meteo.com/v1/flood"
                   f"?latitude={lat}&longitude={lon}"
                   f"&daily=river_discharge,river_discharge_mean"
                   f"&past_days={past_days}&forecast_days=3")
            import urllib.request
            loop = asyncio.get_event_loop()
            def _get():
                with urllib.request.urlopen(url, timeout=15) as r:
                    return json.loads(r.read())
            return await loop.run_in_executor(None, _get)

        data = await with_retry(_live_fetch, retries=2, delays=[3, 10], fallback=None)

        if data:
            self._mem.set(cache_key, data, source="api")
            self._disk.set(cache_key, data, source="api")
            return data

        # Fallback to stale cache
        for entry in (mem_entry, self._disk.get(cache_key)):
            if entry:
                age = entry.age_hours
                log.warning(f"GloFAS API unavailable — serving stale cache "
                             f"for {site_code} (age {age:.1f}h)")
                if self._mode == OperationMode.ONLINE:
                    self._mode = OperationMode.DEGRADED
                return entry.data

        log.error(f"No GloFAS data available for {site_code}")
        return None

    async def fetch_weather_resilient(self, lat: float, lon: float,
                                       city: str) -> Optional[Dict]:
        """Fetch weather with retry + cache fallback."""
        cache_key = f"weather_{city.lower().replace(' ', '_')}"

        mem_entry = self._mem.get(cache_key)
        if mem_entry and mem_entry.is_fresh():
            return mem_entry.data

        async def _live_fetch():
            url = (f"https://api.open-meteo.com/v1/forecast"
                   f"?latitude={lat}&longitude={lon}"
                   f"&current=precipitation,rain,wind_speed_10m,temperature_2m"
                   f"&daily=precipitation_sum,wind_speed_10m_max"
                   f"&past_days=3&forecast_days=3"
                   f"&timezone=Asia%2FKolkata")
            import urllib.request
            loop = asyncio.get_event_loop()
            def _get():
                with urllib.request.urlopen(url, timeout=15) as r:
                    return json.loads(r.read())
            return await loop.run_in_executor(None, _get)

        data = await with_retry(_live_fetch, retries=2, delays=[3, 10], fallback=None)

        if data:
            self._mem.set(cache_key, data, source="api")
            self._disk.set(cache_key, data, source="api")
            return data

        for entry in (mem_entry, self._disk.get(cache_key)):
            if entry:
                log.warning(f"Weather API unavailable — serving stale cache "
                             f"for {city} (age {entry.age_hours:.1f}h)")
                return entry.data

        return None

    # ── Mode report ───────────────────────────────────────────────────────────

    async def get_mode_report(self) -> SystemModeReport:
        """Return a full system mode report including cache stats and recommendations."""
        await self.refresh_health(force=True)

        entries  = self._disk.list_entries()
        oldest_h = max((h for _, h in entries), default=0.0)

        recs: List[str] = []
        mode = self._mode

        if mode == OperationMode.OFFLINE:
            recs += [
                "System is offline — check container network connectivity",
                "Verify Open-Meteo API reachability: curl https://flood-api.open-meteo.com/v1/flood",
                "Last known watershed data may be stale — treat predictions as estimates only",
                "SMS alerts are disabled until connectivity is restored",
            ]
        elif mode == OperationMode.CACHED:
            recs += [
                "Serving last-known-good data from disk cache",
                f"Oldest cached data: {oldest_h:.1f} hours old",
                "Predictions based on cached discharge values — uncertainty is elevated",
                "System will automatically recover when APIs are reachable",
            ]
        elif mode == OperationMode.DEGRADED:
            recs += [
                "Some APIs are unreachable — system is in degraded mode",
                "A mix of live and cached data is being used",
                "Monitor /api/system/mode for recovery status",
            ]
        else:
            recs += ["All systems operational — real-time data is flowing normally"]

        unreachable = [s.name for s in self._source_statuses.values()
                       if not s.reachable]
        if unreachable:
            recs.append(f"Unreachable APIs: {', '.join(unreachable)}")

        msgs = {
            OperationMode.ONLINE:   "All APIs reachable, real-time data active",
            OperationMode.DEGRADED: "Partial connectivity — mixing live and cached data",
            OperationMode.CACHED:   "APIs unreachable — serving from cache",
            OperationMode.OFFLINE:  "System offline — no external data available",
        }

        return SystemModeReport(
            current_mode    = mode.value,
            sources         = list(self._source_statuses.values()),
            cache_entries   = len(entries),
            oldest_cache_h  = round(oldest_h, 1),
            message         = msgs[mode],
            recommendations = recs,
        )

    # ── Cache management ──────────────────────────────────────────────────────

    def clear_stale_cache(self) -> int:
        """Remove cache entries older than TTL_STALE_SECONDS. Returns count deleted."""
        deleted = 0
        for p in self._disk.cache_dir.glob("*.pkl"):
            try:
                with open(p, "rb") as f:
                    entry = pickle.load(f)
                if not entry.is_usable():
                    p.unlink()
                    deleted += 1
            except Exception:
                p.unlink(missing_ok=True)
                deleted += 1
        return deleted

    def warm_cache(self, data: Dict[str, Any]) -> None:
        """Pre-warm cache with provided data dict (key → value)."""
        for key, value in data.items():
            self._mem.set(key, value, source="warm")
            self._disk.set(key, value, source="warm")
        log.info(f"Cache warmed with {len(data)} entries")


# ── Singleton ─────────────────────────────────────────────────────────────────
_manager_singleton: Optional[DataSourceManager] = None


def get_data_manager(cache_dir: str = "/tmp/flood_offline_cache") -> DataSourceManager:
    global _manager_singleton
    if _manager_singleton is None:
        _manager_singleton = DataSourceManager(cache_dir=cache_dir)
    return _manager_singleton
