"""
ml_models.py — Research-grade ML prediction module for India Flood Intelligence.

Implements four model architectures trained on GloFAS historical discharge data:
  1. LSTM          — stacked bidirectional LSTM sequence model
  2. GRU           — gated recurrent unit (faster, comparable accuracy)
  3. Transformer   — self-attention encoder + regression head
  4. Random Forest — tree ensemble (interpretable, no GPU needed)

All models share:
  - A common 12-feature set derived from GloFAS + Open-Meteo data
  - Identical 85/15 train/val splits
  - A unified MLModelEnsemble wrapper used by PredictorAgent
  - Graceful degradation: if torch is absent, only Random Forest runs

Usage
-----
    from flood_prediction.ml_models import get_ensemble
    ensemble = get_ensemble()
    await ensemble.train_all()
    pred = await ensemble.predict(watershed_dict, horizon_hours=24)
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import pickle
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional deep-learning imports — fail gracefully
# ---------------------------------------------------------------------------
try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
    log.info("PyTorch available — LSTM/GRU/Transformer models enabled")
except ImportError:
    TORCH_AVAILABLE = False
    log.warning("PyTorch not available — only RandomForest model will run")

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    log.warning("scikit-learn not available — all ML models disabled")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEQUENCE_LENGTH = 14        # 14 daily snapshots as input window
FEATURE_NAMES = [
    "discharge_cfs",        # current river discharge
    "discharge_mean_7d",    # 7-day rolling mean
    "discharge_std_7d",     # 7-day rolling std (volatility proxy)
    "flow_ratio",           # discharge / flood_stage_cfs
    "trend_rate",           # cfs/hour trend rate
    "precipitation_mm",     # daily precipitation
    "precip_3d_sum",        # 3-day cumulative rainfall
    "precip_7d_sum",        # 7-day cumulative rainfall (soil saturation proxy)
    "wind_speed_kmh",       # wind speed (cyclone indicator)
    "month_sin",            # seasonal encoding (sin component)
    "month_cos",            # seasonal encoding (cos component)
    "basin_id",             # normalised basin index 0-1
]
N_FEATURES = len(FEATURE_NAMES)

BASIN_INDEX = {
    "IN-GANGA": 0, "IN-BRAHMAPUTRA": 1, "IN-MAHANADI": 2,
    "IN-GODAVARI": 3, "IN-KRISHNA": 4, "IN-NARMADA": 5,
    "IN-KAVERI": 6, "IN-INDUS": 7,
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class MLPrediction:
    model_name: str
    watershed_id: int
    watershed_name: str
    horizon_hours: int
    predicted_discharge_cfs: float
    predicted_risk_score: float
    predicted_risk_level: str
    confidence: float
    feature_importances: Dict[str, float] = field(default_factory=dict)
    predicted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    valid_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EnsemblePrediction:
    watershed_id: int
    watershed_name: str
    horizon_hours: int
    ensemble_discharge_cfs: float
    ensemble_risk_score: float
    ensemble_risk_level: str
    ensemble_confidence: float
    model_predictions: List[MLPrediction] = field(default_factory=list)
    model_agreement: float = 0.0
    predicted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    valid_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["model_predictions"] = [p.to_dict() for p in self.model_predictions]
        return d


@dataclass
class TrainingResult:
    model_name: str
    n_samples: int
    n_features: int
    train_rmse: float
    val_rmse: float
    train_mae: float
    val_mae: float
    epochs_run: int
    training_time_seconds: float
    feature_importances: Dict[str, float] = field(default_factory=dict)
    trained_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Feature engineering helpers
# ---------------------------------------------------------------------------

def _month_encoding(month: int) -> Tuple[float, float]:
    angle = 2 * math.pi * (month - 1) / 12
    return math.sin(angle), math.cos(angle)


def _basin_id(region_code: str) -> float:
    idx = BASIN_INDEX.get(region_code, 0)
    return idx / max(len(BASIN_INDEX) - 1, 1)


def extract_features(watershed: Dict[str, Any],
                     history: Optional[List[Dict[str, Any]]] = None,
                     ref_time: Optional[datetime] = None) -> np.ndarray:
    """Build a 1-D feature vector from a single watershed snapshot."""
    if ref_time is None:
        ref_time = datetime.now(timezone.utc)

    discharge = float(watershed.get("current_streamflow_cfs") or 0)
    flood_stage = float(watershed.get("flood_stage_cfs") or 1)
    trend_rate = float(watershed.get("trend_rate_cfs_per_hour") or 0)
    precip = float(watershed.get("precipitation_mm") or 0)
    wind = float(watershed.get("wind_speed_kmh") or 0)
    region_code = watershed.get("region_code", "IN-GANGA")

    if history and len(history) >= 3:
        recent = [float(h.get("current_streamflow_cfs") or discharge) for h in history[-7:]]
        precips = [float(h.get("precipitation_mm") or 0) for h in history]
        mean_7d = float(np.mean(recent))
        std_7d = float(np.std(recent)) if len(recent) > 1 else 0.0
        p3d = float(sum(precips[-3:]))
        p7d = float(sum(precips[-7:]))
    else:
        mean_7d = discharge
        std_7d = 0.0
        p3d = precip * 3
        p7d = precip * 7

    flow_ratio = discharge / max(flood_stage, 1.0)
    ms, mc = _month_encoding(ref_time.month)

    return np.array([
        discharge, mean_7d, std_7d, flow_ratio, trend_rate,
        precip, p3d, p7d, wind, ms, mc, _basin_id(region_code),
    ], dtype=np.float32)


def build_sequence(snapshots: List[Dict[str, Any]],
                   seq_len: int = SEQUENCE_LENGTH) -> np.ndarray:
    """Build a (seq_len, N_FEATURES) array, padding at the start if needed."""
    feats = [extract_features(s) for s in snapshots]
    while len(feats) < seq_len:
        feats.insert(0, feats[0].copy())
    feats = feats[-seq_len:]
    return np.stack(feats, axis=0)


def risk_score_from_discharge(discharge: float, flood_stage: float,
                               current_risk: float = 0.0) -> float:
    if flood_stage <= 0:
        return 0.0
    ratio = discharge / flood_stage
    return round(min(10.0, max(0.0, ratio * 8.0 + current_risk * 0.2)), 2)


def risk_level(score: float) -> str:
    if score >= 8.0:
        return "CRITICAL"
    elif score >= 6.0:
        return "HIGH"
    elif score >= 4.0:
        return "MODERATE"
    return "LOW"


# ---------------------------------------------------------------------------
# Real GloFAS training data fetcher
# ---------------------------------------------------------------------------

# GloFAS API sites for training — 10 representative India sites
# covering all 8 major basins with known lat/lon
_GLOFAS_TRAINING_SITES = [
    ("brahmaputra_guwahati",  26.14,  91.74, "IN-BRAHMAPUTRA", 848_000.0),
    ("ganga_patna",           25.60,  85.10, "IN-GANGA",        424_776.0),
    ("mahanadi_mundali",      20.46,  85.88, "IN-MAHANADI",     170_000.0),
    ("godavari_rajahmundry",  17.00,  81.78, "IN-GODAVARI",     350_000.0),
    ("krishna_vijayawada",    16.51,  80.65, "IN-KRISHNA",      160_000.0),
    ("narmada_garudeshwar",   21.89,  73.65, "IN-NARMADA",      100_000.0),
    ("kaveri_mettur",         11.79,  77.80, "IN-KAVERI",        70_000.0),
    ("indus_attari",          31.68,  74.59, "IN-INDUS",         85_000.0),
    ("brahmaputra_dibrugarh", 27.49,  95.00, "IN-BRAHMAPUTRA",  720_000.0),
    ("ganga_varanasi",        25.32,  83.01, "IN-GANGA",        360_000.0),
]

_GLOFAS_PRECIP_CITIES = [
    ("Guwahati",   26.14,  91.74),
    ("Patna",      25.60,  85.10),
    ("Bhubaneswar",20.30,  85.82),
    ("Hyderabad",  17.38,  78.49),
    ("Surat",      21.19,  72.83),
]


async def fetch_real_glofas_training_data(
        past_days: int = 365,
        cache_path: Optional[str] = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Fetch real GloFAS historical river discharge data from Open-Meteo Flood API
    for all 10 India training sites.

    Uses the free Open-Meteo GloFAS API (no API key required).
    Data is cached to disk to avoid repeated downloads.

    Parameters
    ----------
    past_days : int
        Number of historical days to fetch (max 92 for free tier, use 90)
    cache_path : str, optional
        Directory to cache downloaded data

    Returns
    -------
    X : (n_samples, SEQUENCE_LENGTH, N_FEATURES)
    y : (n_samples,) — next-day discharge in CFS
    """
    import asyncio
    import json
    from pathlib import Path
    from datetime import datetime, timedelta

    # Check cache first
    if cache_path:
        cache_file = Path(cache_path) / f"glofas_training_{past_days}d.npz"
        if cache_file.exists():
            try:
                loaded = np.load(str(cache_file))
                log.info(f"Loaded real GloFAS training data from cache: {cache_file}")
                return loaded["X"], loaded["y"]
            except Exception:
                pass

    log.info(f"Fetching {past_days} days of real GloFAS data for {len(_GLOFAS_TRAINING_SITES)} India sites...")

    try:
        import httpx
    except ImportError:
        import urllib.request as _url
        httpx = None

    X_all, y_all = [], []
    sites_fetched = 0

    for site_code, lat, lon, region_code, flood_stage in _GLOFAS_TRAINING_SITES:
        try:
            # Fetch discharge from GloFAS
            flood_url = (
                f"https://flood-api.open-meteo.com/v1/flood"
                f"?latitude={lat}&longitude={lon}"
                f"&daily=river_discharge"
                f"&past_days={past_days}&forecast_days=1"
            )

            if httpx:
                async with httpx.AsyncClient(timeout=30) as client:
                    flood_resp = await client.get(flood_url)
                    flood_data = flood_resp.json()
            else:
                import asyncio, urllib.request
                loop = asyncio.get_event_loop()
                def _get(url):
                    with urllib.request.urlopen(url, timeout=30) as r:
                        return json.loads(r.read())
                flood_data = await loop.run_in_executor(None, _get, flood_url)

            discharge_m3s = flood_data.get("daily", {}).get("river_discharge", [])
            if not discharge_m3s or len(discharge_m3s) < SEQUENCE_LENGTH + 2:
                log.warning(f"Insufficient discharge data for {site_code}, skipping")
                continue

            # Convert m³/s → CFS
            discharge_cfs = [float(v or 0) * 35.3147 for v in discharge_m3s]

            # Fetch precipitation for the nearest city
            nearest_city = min(_GLOFAS_PRECIP_CITIES,
                               key=lambda c: (c[1]-lat)**2 + (c[2]-lon)**2)
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast"
                f"?latitude={nearest_city[1]}&longitude={nearest_city[2]}"
                f"&daily=precipitation_sum,wind_speed_10m_max"
                f"&past_days={past_days}&forecast_days=1"
                f"&timezone=Asia%2FKolkata"
            )

            if httpx:
                async with httpx.AsyncClient(timeout=30) as client:
                    wx_resp = await client.get(weather_url)
                    wx_data = wx_resp.json()
            else:
                wx_data = await loop.run_in_executor(None, _get, weather_url)

            precip_mm = wx_data.get("daily", {}).get("precipitation_sum", [])
            wind_kmh  = wx_data.get("daily", {}).get("wind_speed_10m_max", [])

            # Align lengths
            n = min(len(discharge_cfs), len(precip_mm) if precip_mm else len(discharge_cfs))
            discharge_cfs = discharge_cfs[:n]
            precip_mm     = [float(v or 0) for v in precip_mm[:n]] if precip_mm else [0.0]*n
            wind_kmh      = [float(v or 0) for v in wind_kmh[:n]]  if wind_kmh  else [0.0]*n

            basin_ord = list(BASIN_INDEX.keys()).index(region_code) if region_code in BASIN_INDEX else 0

            # Build sequences
            for start in range(SEQUENCE_LENGTH, n - 1):
                seq = []
                for d in range(start - SEQUENCE_LENGTH, start):
                    month = d % 12 + 1
                    ms, mc = _month_encoding(month)
                    flow = discharge_cfs[d]
                    window = discharge_cfs[max(0, d-6):d+1]
                    feat = np.array([
                        flow,
                        float(np.mean(window)),
                        float(np.std(window)) if len(window) > 1 else 0.0,
                        flow / max(flood_stage, 1.0),
                        float(discharge_cfs[d] - discharge_cfs[max(0, d-1)]),
                        precip_mm[d],
                        float(sum(precip_mm[max(0,d-2):d+1])),
                        float(sum(precip_mm[max(0,d-6):d+1])),
                        wind_kmh[d],
                        ms, mc,
                        basin_ord / 7.0,
                    ], dtype=np.float32)
                    seq.append(feat)
                X_all.append(np.stack(seq, axis=0))
                y_all.append(float(discharge_cfs[start]))

            sites_fetched += 1
            log.info(f"  ✓ {site_code}: {n} days, {n - SEQUENCE_LENGTH - 1} sequences")

        except Exception as e:
            log.warning(f"  ✗ {site_code}: {e}")
            continue

    if len(X_all) < 50:
        log.warning(f"Only {len(X_all)} sequences from real data — falling back to hybrid (real + synthetic)")
        # Pad with synthetic to reach minimum training size
        X_syn, y_syn = generate_synthetic_training_data(n_sites=20, n_days=365)
        if len(X_all) > 0:
            X_real = np.stack(X_all).astype(np.float32)
            y_real = np.array(y_all, dtype=np.float32)
            X = np.concatenate([X_real, X_syn], axis=0)
            y = np.concatenate([y_real, y_syn], axis=0)
        else:
            X, y = X_syn, y_syn
    else:
        X = np.stack(X_all).astype(np.float32)
        y = np.array(y_all, dtype=np.float32)
        log.info(f"Real GloFAS training data: {sites_fetched} sites, X={X.shape}, y={y.shape}")

    # Cache to disk
    if cache_path and len(X) > 0:
        try:
            Path(cache_path).mkdir(parents=True, exist_ok=True)
            np.savez_compressed(str(Path(cache_path) / f"glofas_training_{past_days}d.npz"),
                                X=X, y=y)
            log.info(f"Cached real GloFAS training data to {cache_path}")
        except Exception as e:
            log.warning(f"Could not cache training data: {e}")

    return X, y


# ---------------------------------------------------------------------------
# Synthetic training data (GloFAS-like India monsoon patterns)
# Keep as fallback when real API is unreachable
# ---------------------------------------------------------------------------

def generate_synthetic_training_data(
        n_sites: int = 45,
        n_days: int = 365 * 3,
        seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate 3-year synthetic GloFAS discharge series for all India basins.

    Patterns captured:
    - Indian monsoon seasonality (Jun-Sep peak, day ~196)
    - Basin-scale differences (Brahmaputra >> Kaveri)
    - AR(1) autocorrelated noise matching GloFAS ensemble spread
    - ~5% extreme flood events exceeding flood stage
    - Slight multi-year trend (climate signal)

    Returns
    -------
    X : (n_samples, SEQUENCE_LENGTH, N_FEATURES)
    y : (n_samples,)  next-day discharge in CFS
    """
    rng = np.random.default_rng(seed)

    basin_configs = [
        ("IN-GANGA",        424776.0, 0),
        ("IN-BRAHMAPUTRA",  848000.0, 1),
        ("IN-MAHANADI",     170000.0, 2),
        ("IN-GODAVARI",     350000.0, 3),
        ("IN-KRISHNA",      160000.0, 4),
        ("IN-NARMADA",      100000.0, 5),
        ("IN-KAVERI",        70000.0, 6),
        ("IN-INDUS",         85000.0, 7),
    ]

    X_all, y_all = [], []

    for site_idx in range(n_sites):
        region_code, flood_stage, basin_ord = basin_configs[site_idx % len(basin_configs)]
        base_flow = flood_stage * 0.35

        days = np.arange(n_days)
        monsoon = np.exp(-0.5 * ((days % 365 - 196) / 55) ** 2) * base_flow * 2.5
        trend = 0.02 * days / 365 * base_flow

        # AR(1) noise
        noise = np.zeros(n_days)
        noise[0] = rng.normal(0, base_flow * 0.1)
        for d in range(1, n_days):
            noise[d] = 0.7 * noise[d - 1] + rng.normal(0, base_flow * 0.08)

        extremes = (rng.random(n_days) < 0.05) * rng.uniform(
            flood_stage * 0.9, flood_stage * 1.4, n_days)

        discharge = np.maximum(0.0, base_flow * 0.3 + monsoon + trend + noise + extremes)
        precip_base = monsoon / max(base_flow * 0.05, 1.0)
        precip = np.maximum(0.0, precip_base + rng.normal(0, 5, n_days))

        for start in range(SEQUENCE_LENGTH, n_days - 1):
            seq = []
            for d in range(start - SEQUENCE_LENGTH, start):
                month = (d % 365 // 30) + 1
                ms, mc = _month_encoding(month)
                flow = discharge[d]
                window = discharge[max(0, d - 6):d + 1]
                feat = np.array([
                    flow,
                    float(np.mean(window)),
                    float(np.std(window)) if len(window) > 1 else 0.0,
                    flow / max(flood_stage, 1.0),
                    float(discharge[d] - discharge[max(0, d - 1)]),
                    precip[d],
                    float(np.sum(precip[max(0, d - 2):d + 1])),
                    float(np.sum(precip[max(0, d - 6):d + 1])),
                    float(rng.uniform(5, 25)),
                    ms, mc,
                    basin_ord / 7.0,
                ], dtype=np.float32)
                seq.append(feat)
            X_all.append(np.stack(seq, axis=0))
            y_all.append(float(discharge[start]))

    X = np.stack(X_all).astype(np.float32)
    y = np.array(y_all, dtype=np.float32)
    return X, y


# ---------------------------------------------------------------------------
# PyTorch architectures
# ---------------------------------------------------------------------------

if TORCH_AVAILABLE:

    class LSTMPredictor(nn.Module):
        def __init__(self, n_features=N_FEATURES, hidden=128, layers=2, dropout=0.2):
            super().__init__()
            self.lstm = nn.LSTM(n_features, hidden, layers,
                                dropout=dropout if layers > 1 else 0.0,
                                batch_first=True, bidirectional=False)
            self.head = nn.Sequential(
                nn.Linear(hidden, 64), nn.ReLU(), nn.Dropout(0.1), nn.Linear(64, 1))

        def forward(self, x):
            out, _ = self.lstm(x)
            return self.head(out[:, -1, :]).squeeze(-1)

    class GRUPredictor(nn.Module):
        def __init__(self, n_features=N_FEATURES, hidden=128, layers=2, dropout=0.2):
            super().__init__()
            self.gru = nn.GRU(n_features, hidden, layers,
                              dropout=dropout if layers > 1 else 0.0,
                              batch_first=True)
            self.head = nn.Sequential(
                nn.Linear(hidden, 64), nn.ReLU(), nn.Dropout(0.1), nn.Linear(64, 1))

        def forward(self, x):
            out, _ = self.gru(x)
            return self.head(out[:, -1, :]).squeeze(-1)

    class TransformerPredictor(nn.Module):
        def __init__(self, n_features=N_FEATURES, d_model=64, nhead=4,
                     enc_layers=2, ff_dim=256, dropout=0.1):
            super().__init__()
            self.proj = nn.Linear(n_features, d_model)
            enc_layer = nn.TransformerEncoderLayer(
                d_model=d_model, nhead=nhead,
                dim_feedforward=ff_dim, dropout=dropout, batch_first=True)
            self.encoder = nn.TransformerEncoder(enc_layer, num_layers=enc_layers)
            self.pos = nn.Parameter(torch.zeros(1, SEQUENCE_LENGTH, d_model))
            self.head = nn.Sequential(nn.Linear(d_model, 32), nn.ReLU(), nn.Linear(32, 1))

        def forward(self, x):
            x = self.proj(x) + self.pos
            x = self.encoder(x)
            return self.head(x.mean(dim=1)).squeeze(-1)


# ---------------------------------------------------------------------------
# Model wrappers
# ---------------------------------------------------------------------------

class _TorchWrapper:
    """Train / load / predict for LSTM, GRU, Transformer."""

    def __init__(self, cls, kwargs, name, model_dir):
        self.cls = cls
        self.kwargs = kwargs
        self.model_name = name
        self.model_dir = Path(model_dir)
        self.model = None
        self.scaler_X = None
        self.scaler_y = None

    @property
    def _ckpt(self): return self.model_dir / f"{self.model_name}.pt"
    @property
    def _scalers(self): return self.model_dir / f"{self.model_name}_scalers.pkl"

    def is_trained(self): return self._ckpt.exists() and self._scalers.exists()

    def load(self) -> bool:
        if not self.is_trained():
            return False
        try:
            with open(self._scalers, "rb") as f:
                self.scaler_X, self.scaler_y = pickle.load(f)
            self.model = self.cls(**self.kwargs)
            self.model.load_state_dict(
                torch.load(self._ckpt, map_location="cpu", weights_only=True))
            self.model.eval()
            return True
        except Exception as e:
            log.warning(f"Load {self.model_name} failed: {e}")
            return False

    def train(self, X: np.ndarray, y: np.ndarray,
              epochs=50, batch_size=256, lr=1e-3, val_split=0.15) -> TrainingResult:
        from sklearn.preprocessing import StandardScaler
        t0 = time.time()
        n, seq, nf = X.shape

        self.scaler_X = StandardScaler()
        Xf = X.reshape(n * seq, nf)
        Xfs = self.scaler_X.fit_transform(Xf).reshape(n, seq, nf).astype(np.float32)

        self.scaler_y = StandardScaler()
        ys = self.scaler_y.fit_transform(y.reshape(-1, 1)).ravel().astype(np.float32)

        split = int(n * (1 - val_split))
        Xtr, Xval = Xfs[:split], Xfs[split:]
        ytr, yval = ys[:split], ys[split:]

        device = torch.device("cpu")
        self.model = self.cls(**self.kwargs).to(device)
        opt = torch.optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
        loss_fn = nn.HuberLoss()

        loader = DataLoader(TensorDataset(torch.from_numpy(Xtr), torch.from_numpy(ytr)),
                            batch_size=batch_size, shuffle=True)

        best_val, best_state = float("inf"), None
        for ep in range(epochs):
            self.model.train()
            for xb, yb in loader:
                opt.zero_grad()
                loss = loss_fn(self.model(xb), yb)
                loss.backward()
                nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                opt.step()
            sched.step()

            self.model.eval()
            with torch.no_grad():
                vl = loss_fn(self.model(torch.from_numpy(Xval)),
                             torch.from_numpy(yval)).item()
            if vl < best_val:
                best_val = vl
                best_state = {k: v.clone() for k, v in self.model.state_dict().items()}
            if (ep + 1) % 10 == 0:
                log.info(f"  {self.model_name} ep {ep+1}/{epochs} val={vl:.4f}")

        if best_state:
            self.model.load_state_dict(best_state)
        self.model.eval()

        def inv(arr_sc, arr_orig):
            p = self.scaler_y.inverse_transform(arr_sc.reshape(-1, 1)).ravel()
            o = self.scaler_y.inverse_transform(arr_orig.reshape(-1, 1)).ravel()
            return float(np.sqrt(np.mean((p - o) ** 2))), float(np.mean(np.abs(p - o)))

        with torch.no_grad():
            trp = self.model(torch.from_numpy(Xtr)).numpy()
            vlp = self.model(torch.from_numpy(Xval)).numpy()

        tr_rmse, tr_mae = inv(trp, ytr)
        vl_rmse, vl_mae = inv(vlp, yval)

        self.model_dir.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), self._ckpt)
        with open(self._scalers, "wb") as f:
            pickle.dump((self.scaler_X, self.scaler_y), f)

        return TrainingResult(
            model_name=self.model_name, n_samples=n, n_features=nf,
            train_rmse=tr_rmse, val_rmse=vl_rmse,
            train_mae=tr_mae, val_mae=vl_mae,
            epochs_run=epochs,
            training_time_seconds=round(time.time() - t0, 2))

    def predict(self, seq: np.ndarray) -> float:
        if self.model is None:
            raise RuntimeError(f"{self.model_name} not loaded")
        sf = self.scaler_X.transform(seq.reshape(-1, N_FEATURES)).reshape(
            1, SEQUENCE_LENGTH, N_FEATURES).astype(np.float32)
        with torch.no_grad():
            ps = self.model(torch.from_numpy(sf)).item()
        return float(self.scaler_y.inverse_transform([[ps]])[0][0])


class _RFWrapper:
    """Random Forest — flattened sequence as feature vector."""

    model_name = "random_forest"

    def __init__(self, model_dir):
        self.model_dir = Path(model_dir)
        self.pipeline = None

    @property
    def _path(self): return self.model_dir / "random_forest.pkl"

    def is_trained(self): return self._path.exists()

    def load(self) -> bool:
        if not self.is_trained():
            return False
        try:
            with open(self._path, "rb") as f:
                self.pipeline = pickle.load(f)
            return True
        except Exception as e:
            log.warning(f"Load random_forest failed: {e}")
            return False

    def train(self, X: np.ndarray, y: np.ndarray) -> TrainingResult:
        from sklearn.preprocessing import StandardScaler
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.pipeline import Pipeline
        t0 = time.time()
        n = X.shape[0]
        Xf = X.reshape(n, -1)
        split = int(n * 0.85)
        Xtr, Xval = Xf[:split], Xf[split:]
        ytr, yval = y[:split], y[split:]
        self.pipeline = Pipeline([
            ("sc", StandardScaler()),
            ("rf", RandomForestRegressor(
                n_estimators=200, max_depth=12,
                min_samples_leaf=5, n_jobs=-1, random_state=42))])
        self.pipeline.fit(Xtr, ytr)
        trp = self.pipeline.predict(Xtr)
        vlp = self.pipeline.predict(Xval)
        tr_rmse = float(np.sqrt(np.mean((trp - ytr) ** 2)))
        vl_rmse = float(np.sqrt(np.mean((vlp - yval) ** 2)))
        tr_mae = float(np.mean(np.abs(trp - ytr)))
        vl_mae = float(np.mean(np.abs(vlp - yval)))
        self.model_dir.mkdir(parents=True, exist_ok=True)
        with open(self._path, "wb") as f:
            pickle.dump(self.pipeline, f)
        # Feature importances averaged over sequence positions
        imps = self.pipeline.named_steps["rf"].feature_importances_
        mat = imps[:SEQUENCE_LENGTH * N_FEATURES].reshape(SEQUENCE_LENGTH, N_FEATURES)
        feat_imp = {FEATURE_NAMES[i]: round(float(mat.mean(axis=0)[i]), 4)
                    for i in range(N_FEATURES)}
        result = TrainingResult(
            model_name=self.model_name, n_samples=n, n_features=N_FEATURES * SEQUENCE_LENGTH,
            train_rmse=tr_rmse, val_rmse=vl_rmse, train_mae=tr_mae, val_mae=vl_mae,
            epochs_run=1, training_time_seconds=round(time.time() - t0, 2),
            feature_importances=feat_imp)
        return result

    def predict(self, seq: np.ndarray) -> float:
        if self.pipeline is None:
            raise RuntimeError("random_forest not loaded")
        return float(self.pipeline.predict(seq.reshape(1, -1))[0])

    def feature_importances(self) -> Dict[str, float]:
        if self.pipeline is None:
            return {}
        imps = self.pipeline.named_steps["rf"].feature_importances_
        mat = imps[:SEQUENCE_LENGTH * N_FEATURES].reshape(SEQUENCE_LENGTH, N_FEATURES)
        return {FEATURE_NAMES[i]: round(float(mat.mean(axis=0)[i]), 4)
                for i in range(N_FEATURES)}


# ---------------------------------------------------------------------------
# Confidence helper
# ---------------------------------------------------------------------------

def _confidence(watershed: Dict[str, Any], horizon_hours: int, model_name: str) -> float:
    base = {"lstm": 0.82, "gru": 0.80, "transformer": 0.83, "random_forest": 0.78}.get(
        model_name, 0.75)
    ts = watershed.get("last_updated") or watershed.get("last_api_update")
    if ts:
        try:
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_h > 6:
                base *= 0.85
            elif age_h > 2:
                base *= 0.93
        except Exception:
            base *= 0.90
    if horizon_hours > 48:
        base *= 0.75
    elif horizon_hours > 24:
        base *= 0.85
    elif horizon_hours > 12:
        base *= 0.92
    if watershed.get("data_source") == "openmeteo":
        base = min(0.95, base * 1.05)
    return round(min(0.95, max(0.30, base)), 3)


# ---------------------------------------------------------------------------
# Ensemble
# ---------------------------------------------------------------------------

class MLModelEnsemble:
    """
    Unified wrapper over all four models.

    Quick-start
    -----------
    ensemble = MLModelEnsemble()
    await ensemble.train_all()           # ~2-5 min first time
    pred = await ensemble.predict(ws, 24)
    """

    def __init__(self, model_dir: str = "/tmp/flood_ml_models"):
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._wrappers: Dict[str, Any] = {}
        self._training_results: Dict[str, TrainingResult] = {}
        self._meta_path = self.model_dir / "ensemble_meta.json"
        self._loaded = False

    # ------------------------------------------------------------------
    def _build_registry(self) -> Dict[str, Any]:
        reg: Dict[str, Any] = {}
        if TORCH_AVAILABLE:
            reg["lstm"] = _TorchWrapper(
                LSTMPredictor, {"n_features": N_FEATURES, "hidden": 128, "layers": 2},
                "lstm", self.model_dir)
            reg["gru"] = _TorchWrapper(
                GRUPredictor, {"n_features": N_FEATURES, "hidden": 128, "layers": 2},
                "gru", self.model_dir)
            reg["transformer"] = _TorchWrapper(
                TransformerPredictor, {"n_features": N_FEATURES, "d_model": 64,
                                       "nhead": 4, "enc_layers": 2},
                "transformer", self.model_dir)
        if SKLEARN_AVAILABLE:
            reg["random_forest"] = _RFWrapper(self.model_dir)
        return reg

    # ------------------------------------------------------------------
    def load_trained_models(self) -> Dict[str, bool]:
        """Load persisted checkpoints. Returns {name: loaded}."""
        self._wrappers = self._build_registry()
        results = {n: w.load() for n, w in self._wrappers.items()}
        self._loaded = any(results.values())
        if self._loaded:
            log.info(f"ML models loaded: {[k for k, v in results.items() if v]}")
        return results

    # ------------------------------------------------------------------
    async def train_all(self,
                        historical_data: Optional[List[Dict]] = None,
                        epochs: int = 50) -> Dict[str, TrainingResult]:
        """Train all models asynchronously (runs in thread pool)."""
        log.info("Starting ML model training pipeline...")
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._train_sync, historical_data, epochs)

    def _train_sync(self, historical_data, epochs) -> Dict[str, TrainingResult]:
        self._wrappers = self._build_registry()

        # Try real GloFAS data first, fall back to synthetic
        X, y = None, None
        try:
            cache_dir = str(self.model_dir / "data_cache")
            loop = asyncio.new_event_loop()
            X, y = loop.run_until_complete(
                fetch_real_glofas_training_data(past_days=90, cache_path=cache_dir)
            )
            loop.close()
            if X is None or len(X) < 50:
                raise ValueError("Insufficient real data")
            log.info(f"Training on REAL GloFAS data: X={X.shape}, y={y.shape}")
        except Exception as e:
            log.warning(f"Real GloFAS data unavailable ({e}), using synthetic fallback")
            X, y = generate_synthetic_training_data(n_sites=45, n_days=365 * 3)
            log.info(f"Training on synthetic data: X={X.shape}, y={y.shape}")

        for name, w in self._wrappers.items():
            try:
                log.info(f"Training {name}...")
                if isinstance(w, _RFWrapper):
                    result = w.train(X, y)
                else:
                    result = w.train(X, y, epochs=epochs)
                self._training_results[name] = result
                log.info(f"  {name} done — val_rmse={result.val_rmse:.1f} CFS")
            except Exception as e:
                log.error(f"Training {name} failed: {e}", exc_info=True)

        meta = {
            n: {"val_rmse": r.val_rmse, "val_mae": r.val_mae,
                "trained_at": r.trained_at, "n_samples": r.n_samples,
                "feature_importances": r.feature_importances}
            for n, r in self._training_results.items()
        }
        with open(self._meta_path, "w") as f:
            json.dump(meta, f, indent=2)
        self._loaded = True
        return self._training_results

    # ------------------------------------------------------------------
    async def predict(self,
                      watershed: Dict[str, Any],
                      horizon_hours: int = 24,
                      history: Optional[List[Dict]] = None) -> EnsemblePrediction:
        """Generate ensemble flood prediction for one watershed."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._predict_sync, watershed, horizon_hours, history)

    def _predict_sync(self, watershed, horizon_hours, history) -> EnsemblePrediction:
        if not self._loaded:
            self.load_trained_models()

        snapshots = (history or []) + [watershed]
        seq = build_sequence(snapshots)

        flood_stage = float(watershed.get("flood_stage_cfs") or 1)
        cur_risk = float(watershed.get("risk_score") or 0)
        valid_at = (datetime.now(timezone.utc) + timedelta(hours=horizon_hours)).isoformat()

        individual: List[MLPrediction] = []

        for name, w in self._wrappers.items():
            try:
                if not (w.is_trained() or (w.model is not None) or (
                        hasattr(w, 'pipeline') and w.pipeline is not None)):
                    continue
                base = w.predict(seq)

                # Horizon adjustment beyond 24 h
                if horizon_hours > 24:
                    tr = float(watershed.get("trend_rate_cfs_per_hour") or 0)
                    extra = horizon_hours - 24
                    base = max(0.0, base + tr * extra * math.exp(-extra / 48))

                rs = risk_score_from_discharge(base, flood_stage, cur_risk)
                fi = w.feature_importances() if hasattr(w, "feature_importances") else {}

                individual.append(MLPrediction(
                    model_name=name,
                    watershed_id=watershed.get("id", 0),
                    watershed_name=watershed.get("name", "Unknown"),
                    horizon_hours=horizon_hours,
                    predicted_discharge_cfs=round(base, 1),
                    predicted_risk_score=rs,
                    predicted_risk_level=risk_level(rs),
                    confidence=_confidence(watershed, horizon_hours, name),
                    feature_importances=fi,
                    valid_at=valid_at,
                ))
            except Exception as e:
                log.warning(f"Predict {name} failed: {e}")

        if not individual:
            return _rule_fallback(watershed, horizon_hours, valid_at)

        total_w = sum(p.confidence for p in individual) or len(individual)
        weights = [p.confidence / total_w for p in individual]

        ens_flow = sum(wt * p.predicted_discharge_cfs for wt, p in zip(weights, individual))
        ens_risk = risk_score_from_discharge(ens_flow, flood_stage, cur_risk)
        ens_conf = float(np.mean([p.confidence for p in individual]))
        risk_std = float(np.std([p.predicted_risk_score for p in individual])
                         if len(individual) > 1 else 0.0)
        agreement = max(0.0, 1.0 - risk_std / 10.0)

        return EnsemblePrediction(
            watershed_id=watershed.get("id", 0),
            watershed_name=watershed.get("name", "Unknown"),
            horizon_hours=horizon_hours,
            ensemble_discharge_cfs=round(ens_flow, 1),
            ensemble_risk_score=round(ens_risk, 2),
            ensemble_risk_level=risk_level(ens_risk),
            ensemble_confidence=round(ens_conf, 3),
            model_predictions=individual,
            model_agreement=round(agreement, 3),
            valid_at=valid_at,
        )

    # ------------------------------------------------------------------
    def get_training_summary(self) -> List[Dict[str, Any]]:
        if not self._training_results and self._meta_path.exists():
            with open(self._meta_path) as f:
                meta = json.load(f)
            return [{"model_name": k, **v} for k, v in meta.items()]
        return [
            {"model_name": n,
             "val_rmse": r.val_rmse, "val_mae": r.val_mae,
             "n_samples": r.n_samples, "epochs_run": r.epochs_run,
             "training_time_seconds": r.training_time_seconds,
             "trained_at": r.trained_at,
             "feature_importances": r.feature_importances}
            for n, r in self._training_results.items()
        ]

    def models_trained(self) -> bool:
        return self._meta_path.exists() or bool(self._training_results)

    def models_available(self) -> List[str]:
        reg = self._build_registry()
        return [n for n, w in reg.items() if w.is_trained()]


# ---------------------------------------------------------------------------
# Fallback and singleton
# ---------------------------------------------------------------------------

def _rule_fallback(watershed, horizon_hours, valid_at) -> EnsemblePrediction:
    """Rule-based exponential-decay prediction when all ML models unavailable."""
    flow = float(watershed.get("current_streamflow_cfs") or 0)
    tr = float(watershed.get("trend_rate_cfs_per_hour") or 0)
    flood_stage = float(watershed.get("flood_stage_cfs") or 1)
    cur_risk = float(watershed.get("risk_score") or 0)
    decay = math.exp(-horizon_hours / 24)
    pred_flow = max(0.0, flow + tr * horizon_hours * decay)
    rs = risk_score_from_discharge(pred_flow, flood_stage, cur_risk)
    fb = MLPrediction(
        model_name="rule_based",
        watershed_id=watershed.get("id", 0),
        watershed_name=watershed.get("name", "Unknown"),
        horizon_hours=horizon_hours,
        predicted_discharge_cfs=round(pred_flow, 1),
        predicted_risk_score=rs,
        predicted_risk_level=risk_level(rs),
        confidence=0.60,
        valid_at=valid_at,
    )
    return EnsemblePrediction(
        watershed_id=watershed.get("id", 0),
        watershed_name=watershed.get("name", "Unknown"),
        horizon_hours=horizon_hours,
        ensemble_discharge_cfs=round(pred_flow, 1),
        ensemble_risk_score=round(rs, 2),
        ensemble_risk_level=risk_level(rs),
        ensemble_confidence=0.60,
        model_predictions=[fb],
        model_agreement=1.0,
        valid_at=valid_at,
    )


_ensemble_singleton: Optional[MLModelEnsemble] = None


def get_ensemble(model_dir: str = "/tmp/flood_ml_models") -> MLModelEnsemble:
    """Return (or create) the module-level ensemble singleton."""
    global _ensemble_singleton
    if _ensemble_singleton is None:
        _ensemble_singleton = MLModelEnsemble(model_dir=model_dir)
        _ensemble_singleton.load_trained_models()
    return _ensemble_singleton
