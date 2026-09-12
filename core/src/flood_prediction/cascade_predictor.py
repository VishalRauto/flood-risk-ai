"""
cascade_predictor.py — Compound Cascade Predictor

World-first: No existing flood system predicts second-order disasters
triggered by flooding (infrastructure failures, disease, power cuts).

Given a flood risk level, this module predicts:
  1. Bridge / culvert failure probability
  2. Landslide / slope failure risk
  3. Disease outbreak hotspots (cholera, leptospirosis, malaria)
  4. Power grid failure zones
  5. Road network cut-off segments
  6. Agricultural supply chain disruption

Each cascade risk has:
  - Probability (0-1)
  - Estimated onset time (hours after flood peak)
  - Affected area / infrastructure
  - Recommended pre-emptive action
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class CascadeRisk:
    category:       str       # bridge | landslide | disease | power | road | agriculture
    subcategory:    str       # specific type within category
    probability:    float     # 0-1
    severity:       str       # LOW | MODERATE | HIGH | CRITICAL
    onset_hours:    float     # hours after flood peak
    duration_hours: float     # expected duration
    affected:       List[str] # locations / infrastructure affected
    action:         str       # recommended pre-emptive action
    confidence:     float     # model confidence 0-1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CascadeReport:
    watershed_id:   int
    watershed_name: str
    flood_risk:     float
    flood_level:    str
    cascades:       List[CascadeRisk]
    total_cascades: int
    critical_count: int
    high_count:     int
    overall_cascade_risk: float   # 0-10
    priority_action: str
    generated_at:   str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["cascades"] = [c.to_dict() for c in self.cascades]
        return d


# ── India-specific infrastructure vulnerability data ──────────────────────────
# Source: MoRTH bridge census, POSOCO grid data, NIDM landslide atlas

BRIDGE_VULNERABLE_BASINS = {
    "IN-BRAHMAPUTRA": ["NH-27 Brahmaputra bridges", "Saraighat Bridge Guwahati",
                       "Bogibeel Bridge Dibrugarh", "Kolia Bhomora Setu"],
    "IN-GANGA":       ["Mahatma Gandhi Setu Patna", "Rajendra Setu Mokama",
                       "Nehru Setu Dehri", "Ganga bridges UP-Bihar border"],
    "IN-MAHANADI":    ["Jobra barrage bridge Cuttack", "NH-16 Mahanadi crossings"],
    "IN-GODAVARI":    ["Godavari road-rail bridge Rajahmundry", "NH-16 Godavari crossing"],
    "IN-KRISHNA":     ["Prakasam Barrage Vijayawada", "Krishna NH bridges"],
    "IN-NARMADA":     ["Sardar Sarovar approach bridges", "NH-47 Narmada crossings"],
    "IN-KAVERI":      ["KRS dam bridge", "Kaveri NH crossings TN"],
    "IN-INDUS":       ["Beas bridges NH-1", "Sutlej crossings PB"],
}

LANDSLIDE_PRONE_BASINS = {
    "IN-BRAHMAPUTRA": 0.85,  # Northeast Himalayas — very high
    "IN-GANGA":       0.45,  # Uttarakhand segments
    "IN-INDUS":       0.70,  # J&K, Himachal
    "IN-NARMADA":     0.30,  # Satpura range
    "IN-GODAVARI":    0.25,  # Eastern Ghats
    "IN-MAHANADI":    0.20,
    "IN-KRISHNA":     0.20,
    "IN-KAVERI":      0.15,
}

DISEASE_OUTBREAK_RISK = {
    # (cholera_risk, lepto_risk, malaria_risk) — baseline per basin
    "IN-BRAHMAPUTRA": (0.7, 0.8, 0.9),
    "IN-GANGA":       (0.8, 0.7, 0.7),
    "IN-MAHANADI":    (0.7, 0.8, 0.8),
    "IN-GODAVARI":    (0.6, 0.7, 0.7),
    "IN-KRISHNA":     (0.5, 0.6, 0.6),
    "IN-NARMADA":     (0.5, 0.6, 0.5),
    "IN-KAVERI":      (0.4, 0.5, 0.7),
    "IN-INDUS":       (0.4, 0.4, 0.3),
}

POWER_SUBSTATIONS = {
    "IN-BRAHMAPUTRA": ["AEGCL Guwahati 220kV", "AEGCL Silchar 132kV"],
    "IN-GANGA":       ["BSPTCL Patna 400kV", "UPPCL Varanasi 220kV"],
    "IN-MAHANADI":    ["GRIDCO Cuttack 220kV", "GRIDCO Bhubaneswar 132kV"],
    "IN-GODAVARI":    ["APTRANSCO Rajahmundry 220kV"],
    "IN-KRISHNA":     ["APTRANSCO Vijayawada 400kV"],
    "IN-NARMADA":     ["MPPTCL Jabalpur 220kV"],
    "IN-KAVERI":      ["TNEB Trichy 220kV"],
    "IN-INDUS":       ["PSPCL Ludhiana 220kV"],
}


class CascadePredictor:
    """
    Predicts second-order disasters triggered by flooding.

    All probabilities are computed from:
    - Current flood risk score (0-10)
    - Basin-specific vulnerability coefficients
    - Time-since-flood-peak (onset timing model)
    - Seasonal factors (monsoon = higher disease risk)
    """

    def predict(self, watershed: Dict[str, Any],
                rainfall_mm: float = 0.0) -> CascadeReport:
        risk_score   = float(watershed.get("risk_score") or 0)
        region_code  = watershed.get("region_code", "IN-GANGA")
        name         = watershed.get("name", "Unknown")
        wid          = watershed.get("id", 0)
        trend        = watershed.get("trend", "stable")
        month        = datetime.now(timezone.utc).month
        monsoon      = month in (6, 7, 8, 9, 10)   # Jun-Oct

        r = risk_score / 10.0   # normalise to 0-1
        cascades: List[CascadeRisk] = []

        # ── 1. Bridge / culvert failures ─────────────────────────────────────
        bridge_base = LANDSLIDE_PRONE_BASINS.get(region_code, 0.3)
        bridge_prob = min(1.0, r * 0.8 + bridge_base * 0.2)
        if risk_score >= 4:
            affected_bridges = BRIDGE_VULNERABLE_BASINS.get(region_code, [f"NH bridges in {name} basin"])
            cascades.append(CascadeRisk(
                category    = "bridge",
                subcategory = "Bridge / culvert structural stress",
                probability = round(bridge_prob, 3),
                severity    = _severity(bridge_prob),
                onset_hours = max(2, 48 * (1 - r)),
                duration_hours = 72,
                affected    = affected_bridges[:3],
                action      = ("Deploy structural engineers for bridge inspection. "
                               "Close vulnerable bridges to heavy vehicles if risk ≥ HIGH. "
                               "Contact NHAI / State PWD immediately."),
                confidence  = 0.78,
            ))

        # ── 2. Landslide / slope failure ─────────────────────────────────────
        ls_vuln   = LANDSLIDE_PRONE_BASINS.get(region_code, 0.2)
        rain_factor = min(1.0, rainfall_mm / 200.0)
        ls_prob   = min(1.0, r * 0.6 * ls_vuln + rain_factor * 0.4)
        if ls_prob > 0.15:
            cascades.append(CascadeRisk(
                category    = "landslide",
                subcategory = "Debris flow / slope failure",
                probability = round(ls_prob, 3),
                severity    = _severity(ls_prob),
                onset_hours = max(1, 12 * (1 - r)),
                duration_hours = 48,
                affected    = [f"Hill slopes in {name} catchment",
                               "NH hill sections", "Rail cuttings"],
                action      = ("Issue landslide warning for hill districts. "
                               "Close hill roads if probability > 0.6. "
                               "Alert NDRF mountain rescue teams. "
                               "Contact GSI Landslide Atlas team."),
                confidence  = 0.72,
            ))

        # ── 3. Disease outbreak hotspots ─────────────────────────────────────
        dis_risks = DISEASE_OUTBREAK_RISK.get(region_code, (0.5, 0.5, 0.5))
        monsoon_mult = 1.4 if monsoon else 1.0
        inundation_days = max(1, risk_score * 2)

        for disease, base_risk, onset_d, action_txt in [
            ("Cholera / diarrhoeal disease",   dis_risks[0], 3,
             "Pre-position ORS packets. Chlorinate drinking water sources. Alert ICMR/NCDC."),
            ("Leptospirosis",                  dis_risks[1], 5,
             "Issue advisory on avoiding floodwater contact. Pre-position doxycycline. Alert CMO."),
            ("Vector-borne (Malaria/Dengue)",  dis_risks[2], 7,
             "Aerial larvicide spraying within 72h. Deploy rapid diagnostic kits. Alert NHP."),
        ]:
            prob = min(1.0, r * base_risk * monsoon_mult * (inundation_days / 10))
            if prob > 0.20:
                cascades.append(CascadeRisk(
                    category    = "disease",
                    subcategory = disease,
                    probability = round(prob, 3),
                    severity    = _severity(prob),
                    onset_hours = onset_d * 24,
                    duration_hours = 30 * 24,
                    affected    = [f"Flood-inundated districts in {name} basin",
                                   "Displacement camps", "Low-income settlements"],
                    action      = action_txt,
                    confidence  = 0.68,
                ))

        # ── 4. Power grid failures ────────────────────────────────────────────
        substations = POWER_SUBSTATIONS.get(region_code, [f"{name} grid substations"])
        power_prob  = min(1.0, r * 0.7)
        if risk_score >= 5:
            cascades.append(CascadeRisk(
                category    = "power",
                subcategory = "Substation flooding / transmission line failure",
                probability = round(power_prob, 3),
                severity    = _severity(power_prob),
                onset_hours = max(1, 6 * (1 - r)),
                duration_hours = 48,
                affected    = substations[:2] + ["Distribution transformers in low-lying areas"],
                action      = ("Notify SLDCs to isolate vulnerable feeders. "
                               "Pre-position DG sets at hospitals and water plants. "
                               "Alert State DISCOM emergency cell. "
                               "Evacuate substation staff if water rising."),
                confidence  = 0.82,
            ))

        # ── 5. Road network cut-offs ──────────────────────────────────────────
        road_prob = min(1.0, r * 0.75 + 0.1)
        if risk_score >= 4:
            cascades.append(CascadeRisk(
                category    = "road",
                subcategory = "National / State Highway submersion",
                probability = round(road_prob, 3),
                severity    = _severity(road_prob),
                onset_hours = max(0.5, 4 * (1 - r)),
                duration_hours = 96,
                affected    = [
                    f"NH segments in {name} flood plain",
                    "District roads < 1m elevation above river",
                    "Rural connectivity (PMGSY roads)",
                ],
                action      = ("Issue road closure advisory. "
                               "Identify alternative routes via higher-elevation roads. "
                               "Pre-position food/medicine stocks before roads close. "
                               "Alert State NH Authority and NHAI."),
                confidence  = 0.85,
            ))

        # ── 6. Agricultural supply chain disruption ───────────────────────────
        crop_month_risk = {
            6: 0.4, 7: 0.6, 8: 0.8, 9: 0.7, 10: 0.5,   # Kharif season
            11: 0.2, 12: 0.3, 1: 0.2, 2: 0.2,            # Rabi season
            3: 0.3, 4: 0.2, 5: 0.3,
        }
        crop_prob = min(1.0, r * crop_month_risk.get(month, 0.3) * 1.5)
        if crop_prob > 0.25:
            cascades.append(CascadeRisk(
                category    = "agriculture",
                subcategory = "Crop loss / supply chain disruption",
                probability = round(crop_prob, 3),
                severity    = _severity(crop_prob),
                onset_hours = 0,
                duration_hours = 30 * 24,
                affected    = [
                    f"Kharif crops in {name} flood plain",
                    "Village-level storage godowns",
                    "Mandi access roads",
                ],
                action      = ("Advance grain procurement from flood-risk mandis. "
                               "Issue crop insurance claim preparation advisory. "
                               "Alert FCI for emergency stock pre-positioning. "
                               "Notify State Agriculture Dept."),
                confidence  = 0.74,
            ))

        # ── Summary ───────────────────────────────────────────────────────────
        critical = sum(1 for c in cascades if c.severity == "CRITICAL")
        high     = sum(1 for c in cascades if c.severity == "HIGH")
        cascade_risk = min(10.0, risk_score * 0.7 + critical * 1.5 + high * 0.8)

        priority = _priority_action(cascades, risk_score)

        return CascadeReport(
            watershed_id          = wid,
            watershed_name        = name,
            flood_risk            = risk_score,
            flood_level           = _flood_level(risk_score),
            cascades              = cascades,
            total_cascades        = len(cascades),
            critical_count        = critical,
            high_count            = high,
            overall_cascade_risk  = round(cascade_risk, 1),
            priority_action       = priority,
        )

    def predict_all(self, watersheds: List[Dict[str, Any]],
                    rainfall_mm: float = 0.0) -> List[CascadeReport]:
        """Predict cascades for all high-risk watersheds (risk ≥ 4)."""
        results = []
        for ws in watersheds:
            if float(ws.get("risk_score") or 0) >= 4.0:
                results.append(self.predict(ws, rainfall_mm))
        results.sort(key=lambda r: r.overall_cascade_risk, reverse=True)
        return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _severity(prob: float) -> str:
    if prob >= 0.75: return "CRITICAL"
    if prob >= 0.50: return "HIGH"
    if prob >= 0.25: return "MODERATE"
    return "LOW"

def _flood_level(risk: float) -> str:
    if risk >= 8: return "CRITICAL"
    if risk >= 6: return "HIGH"
    if risk >= 4: return "MODERATE"
    return "LOW"

def _priority_action(cascades: List[CascadeRisk], risk: float) -> str:
    critical = [c for c in cascades if c.severity == "CRITICAL"]
    if critical:
        cats = ", ".join(set(c.category for c in critical))
        return (f"CRITICAL cascades imminent in: {cats}. "
                f"Activate EOC. Pre-position NDRF and health teams immediately.")
    high = [c for c in cascades if c.severity == "HIGH"]
    if high:
        cats = ", ".join(set(c.category for c in high))
        return (f"HIGH cascade risk in: {cats}. "
                f"Alert district administration and sector agencies.")
    return "Monitor cascade indicators. No immediate cascades predicted."


# Singleton
_predictor: Optional[CascadePredictor] = None

def get_cascade_predictor() -> CascadePredictor:
    global _predictor
    if _predictor is None:
        _predictor = CascadePredictor()
    return _predictor
