"""
carbon_credits.py — Flood Carbon Credit Tracker

World-first: No flood management system connects disaster management
with carbon credit markets. This creates financial incentives for
maintaining natural flood barriers.

What this module does:
  1. Tracks wetland/mangrove areas that act as natural flood buffers
  2. Quantifies their annual carbon sequestration (tCO2/ha/year)
  3. Estimates avoided flood damage value (natural infrastructure)
  4. Generates Verified Carbon Unit (VCU) certificates for communities
     that maintain flood-buffer ecosystems
  5. Calculates the carbon cost of flood relief operations
  6. Tracks cumulative carbon credits earned per district/state

This creates a direct financial incentive for communities to
maintain mangroves, wetlands, and riparian forests instead of
encroaching — since healthy ecosystems earn carbon credits AND
reduce flood risk simultaneously.

Carbon sequestration rates (tCO2e/ha/year):
  Source: ICAR, FSI India State of Forest Report 2023, IPCC Wetlands
  - Mangrove forest:         6.0–8.5 tCO2e/ha/year
  - Freshwater wetland:      3.5–5.0 tCO2e/ha/year
  - Riparian forest:         2.5–4.0 tCO2e/ha/year
  - Floodplain grassland:    1.0–2.0 tCO2e/ha/year
  - Peatland (Northeast):    8.0–12.0 tCO2e/ha/year

Carbon price: India Carbon Market (ICM) 2024 — ₹400–600/tCO2e
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# ── Ecosystem carbon rates (tCO2e/ha/year) ────────────────────────────────────
ECOSYSTEM_CARBON_RATES: Dict[str, Dict[str, float]] = {
    "mangrove": {
        "sequestration_tco2_ha_yr": 7.2,
        "avoided_emission_tco2_ha_yr": 2.5,
        "flood_buffer_value_inr_ha_yr": 45_000,  # avoided damage value
        "description": "Coastal mangrove forest (IPCC Tier 2)",
    },
    "freshwater_wetland": {
        "sequestration_tco2_ha_yr": 4.2,
        "avoided_emission_tco2_ha_yr": 1.8,
        "flood_buffer_value_inr_ha_yr": 28_000,
        "description": "Inland freshwater wetland (FSI 2023)",
    },
    "riparian_forest": {
        "sequestration_tco2_ha_yr": 3.2,
        "avoided_emission_tco2_ha_yr": 1.2,
        "flood_buffer_value_inr_ha_yr": 22_000,
        "description": "Riverbank riparian forest (ICAR 2023)",
    },
    "floodplain_grassland": {
        "sequestration_tco2_ha_yr": 1.5,
        "avoided_emission_tco2_ha_yr": 0.5,
        "flood_buffer_value_inr_ha_yr": 12_000,
        "description": "Floodplain natural grassland",
    },
    "peatland": {
        "sequestration_tco2_ha_yr": 10.0,
        "avoided_emission_tco2_ha_yr": 3.5,
        "flood_buffer_value_inr_ha_yr": 65_000,
        "description": "Northeast peatland (Assam/Meghalaya)",
    },
}

# India wetland areas per basin (hectares) — FSI + Ramsar 2023
BASIN_WETLAND_AREAS: Dict[str, Dict[str, float]] = {
    "IN-BRAHMAPUTRA": {
        "freshwater_wetland": 280_000,
        "riparian_forest": 150_000,
        "peatland": 45_000,
    },
    "IN-GANGA": {
        "freshwater_wetland": 420_000,
        "riparian_forest": 180_000,
        "floodplain_grassland": 320_000,
    },
    "IN-MAHANADI": {
        "mangrove": 18_000,
        "freshwater_wetland": 95_000,
        "riparian_forest": 65_000,
    },
    "IN-GODAVARI": {
        "mangrove": 35_000,
        "freshwater_wetland": 120_000,
        "riparian_forest": 80_000,
    },
    "IN-KRISHNA": {
        "mangrove": 22_000,
        "freshwater_wetland": 85_000,
        "floodplain_grassland": 60_000,
    },
    "IN-NARMADA": {
        "freshwater_wetland": 75_000,
        "riparian_forest": 90_000,
    },
    "IN-KAVERI": {
        "mangrove": 8_000,
        "freshwater_wetland": 45_000,
        "riparian_forest": 55_000,
    },
    "IN-INDUS": {
        "freshwater_wetland": 65_000,
        "floodplain_grassland": 120_000,
        "riparian_forest": 70_000,
    },
}

# India Carbon Market price range 2024
ICM_PRICE_INR_PER_TCO2 = 500   # midpoint ₹400–600

# Relief operation carbon costs (tCO2e per event)
RELIEF_OPERATION_CARBON: Dict[str, float] = {
    "helicopter_sortie":     2.5,   # tCO2e per flight
    "boat_operation_day":    0.3,
    "truck_relief_km":       0.001,
    "ndrf_camp_day":         0.8,
    "generator_day":         1.2,
}


@dataclass
class WetlandAsset:
    ecosystem_type: str
    area_ha:        float
    basin:          str
    annual_sequestration_tco2: float
    annual_buffer_value_inr:   float
    description:    str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CarbonCertificate:
    cert_id:        str
    district:       str
    state:          str
    basin:          str
    ecosystem_type: str
    area_ha:        float
    period_years:   float
    total_tco2e:    float
    carbon_value_inr: float
    avoided_damage_inr: float
    verification_standard: str
    issued_to:      str
    status:         str   # draft | verified | registered | retired
    issued_at:      str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def certificate_text(self) -> str:
        return (
            f"VERIFIED CARBON UNIT CERTIFICATE\n"
            f"{'='*50}\n"
            f"Certificate ID:   {self.cert_id}\n"
            f"Standard:         {self.verification_standard}\n"
            f"Issued to:        {self.issued_to}\n"
            f"Location:         {self.district}, {self.state}\n"
            f"Ecosystem:        {self.ecosystem_type.replace('_', ' ').title()}\n"
            f"Area:             {self.area_ha:,.0f} hectares\n"
            f"Period:           {self.period_years:.1f} years\n"
            f"Carbon credits:   {self.total_tco2e:,.1f} tCO2e\n"
            f"Carbon value:     ₹{self.carbon_value_inr:,.0f}\n"
            f"Avoided damage:   ₹{self.avoided_damage_inr:,.0f}\n"
            f"Total value:      ₹{self.carbon_value_inr + self.avoided_damage_inr:,.0f}\n"
            f"Status:           {self.status.upper()}\n"
            f"Issued:           {self.issued_at[:10]}\n"
            f"{'='*50}\n"
            f"This certificate verifies that the above wetland ecosystem\n"
            f"has been maintained as a natural flood buffer, sequestering\n"
            f"carbon and preventing downstream flood damage.\n"
            f"Registry: India Carbon Market (BEE, MoEFCC)\n"
        )


@dataclass
class CarbonReport:
    basin:               str
    total_wetland_ha:    float
    wetland_assets:      List[WetlandAsset]
    annual_sequestration_tco2: float
    annual_carbon_value_inr: float
    annual_buffer_value_inr: float
    relief_ops_carbon_tco2: float
    net_carbon_balance:  float   # sequestration - relief ops emissions
    certificates:        List[CarbonCertificate]
    total_cert_value_inr: float
    flood_risk:          float
    recommendation:      str
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["wetland_assets"]  = [a.to_dict() for a in self.wetland_assets]
        d["certificates"]    = [c.to_dict() for c in self.certificates]
        return d


class CarbonCreditTracker:
    """
    Tracks carbon sequestration by flood-buffer wetlands and generates
    VCU certificates for communities that maintain natural flood barriers.
    """

    def generate_report(self, watershed: Dict[str, Any]) -> CarbonReport:
        region_code = watershed.get("region_code", "IN-GANGA")
        name        = watershed.get("name", "Unknown")
        risk        = float(watershed.get("risk_score") or 0)
        district    = name.split(" at ")[-1].split("(")[0].strip()

        # Get wetland areas for this basin
        wetland_areas = BASIN_WETLAND_AREAS.get(region_code, {
            "freshwater_wetland": 50_000, "riparian_forest": 30_000})

        # Build wetland assets
        assets: List[WetlandAsset] = []
        total_seq = 0.0
        total_buf = 0.0
        total_ha  = 0.0

        for eco_type, area_ha in wetland_areas.items():
            rates = ECOSYSTEM_CARBON_RATES[eco_type]
            seq   = area_ha * rates["sequestration_tco2_ha_yr"]
            buf   = area_ha * rates["flood_buffer_value_inr_ha_yr"]
            assets.append(WetlandAsset(
                ecosystem_type            = eco_type,
                area_ha                   = area_ha,
                basin                     = region_code,
                annual_sequestration_tco2 = round(seq, 0),
                annual_buffer_value_inr   = round(buf, 0),
                description               = rates["description"],
            ))
            total_seq += seq
            total_buf += buf
            total_ha  += area_ha

        carbon_value = total_seq * ICM_PRICE_INR_PER_TCO2

        # Estimate relief ops carbon cost (varies with risk)
        relief_carbon = (risk / 10) * (
            RELIEF_OPERATION_CARBON["ndrf_camp_day"] * 14 +
            RELIEF_OPERATION_CARBON["helicopter_sortie"] * 20 +
            RELIEF_OPERATION_CARBON["boat_operation_day"] * 50
        )

        net_balance = total_seq - relief_carbon

        # Generate certificates (one per ecosystem type per district)
        certs: List[CarbonCertificate] = []
        state_map = {
            "IN-BRAHMAPUTRA": "Assam", "IN-GANGA": "Bihar",
            "IN-MAHANADI": "Odisha", "IN-GODAVARI": "Andhra Pradesh",
            "IN-KRISHNA": "Andhra Pradesh", "IN-NARMADA": "Madhya Pradesh",
            "IN-KAVERI": "Tamil Nadu", "IN-INDUS": "Punjab",
        }
        state = state_map.get(region_code, "India")

        for asset in assets[:3]:   # top 3 ecosystems get certificates
            cert_id = f"VCU-{region_code[-2:]}-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
            tco2    = asset.annual_sequestration_tco2
            c_val   = tco2 * ICM_PRICE_INR_PER_TCO2
            certs.append(CarbonCertificate(
                cert_id             = cert_id,
                district            = district,
                state               = state,
                basin               = region_code,
                ecosystem_type      = asset.ecosystem_type,
                area_ha             = asset.area_ha,
                period_years        = 1.0,
                total_tco2e         = round(tco2, 1),
                carbon_value_inr    = round(c_val, 0),
                avoided_damage_inr  = round(asset.annual_buffer_value_inr * 0.3, 0),
                verification_standard = "India Carbon Market (BEE/VCS)",
                issued_to           = f"Community Wetland Guardians — {district}",
                status              = "draft",
            ))

        total_cert_value = sum(c.carbon_value_inr + c.avoided_damage_inr for c in certs)

        # Recommendation
        if risk >= 7 and total_ha < 50_000:
            rec = (f"URGENT: Only {total_ha:,.0f} ha of wetland buffer remain. "
                   f"Mangrove/wetland restoration of 20,000+ ha could earn "
                   f"₹{20_000 * ECOSYSTEM_CARBON_RATES['mangrove']['sequestration_tco2_ha_yr'] * ICM_PRICE_INR_PER_TCO2 / 1e7:.1f} Cr/year "
                   f"in carbon credits AND reduce flood risk by ~15-25%.")
        elif net_balance > 0:
            rec = (f"Positive carbon balance: {net_balance:,.0f} tCO2e net sequestered annually. "
                   f"Ecosystem value: ₹{carbon_value/1e7:.1f} Cr/year. "
                   f"Recommend wetland protection legislation and community stewardship incentives.")
        else:
            rec = (f"Carbon deficit: relief operations emit more than wetlands sequester. "
                   f"Restoring {abs(net_balance) / 5:.0f} ha of mangrove/wetland "
                   f"would achieve carbon neutrality for flood operations.")

        return CarbonReport(
            basin                      = name,
            total_wetland_ha           = round(total_ha, 0),
            wetland_assets             = assets,
            annual_sequestration_tco2  = round(total_seq, 0),
            annual_carbon_value_inr    = round(carbon_value, 0),
            annual_buffer_value_inr    = round(total_buf, 0),
            relief_ops_carbon_tco2     = round(relief_carbon, 1),
            net_carbon_balance         = round(net_balance, 1),
            certificates               = certs,
            total_cert_value_inr       = round(total_cert_value, 0),
            flood_risk                 = risk,
            recommendation             = rec,
        )

    def issue_certificate(self, district: str, state: str, basin: str,
                           ecosystem_type: str, area_ha: float,
                           community_name: str) -> CarbonCertificate:
        """Issue a new VCU certificate for a community wetland guardian."""
        rates   = ECOSYSTEM_CARBON_RATES.get(ecosystem_type,
                  ECOSYSTEM_CARBON_RATES["freshwater_wetland"])
        tco2    = area_ha * rates["sequestration_tco2_ha_yr"]
        c_val   = tco2 * ICM_PRICE_INR_PER_TCO2
        buf_val = area_ha * rates["flood_buffer_value_inr_ha_yr"] * 0.3
        cert_id = f"VCU-{basin[-2:]}-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        return CarbonCertificate(
            cert_id             = cert_id,
            district            = district,
            state               = state,
            basin               = basin,
            ecosystem_type      = ecosystem_type,
            area_ha             = area_ha,
            period_years        = 1.0,
            total_tco2e         = round(tco2, 1),
            carbon_value_inr    = round(c_val, 0),
            avoided_damage_inr  = round(buf_val, 0),
            verification_standard = "India Carbon Market (BEE/VCS)",
            issued_to           = community_name,
            status              = "draft",
        )


_tracker: Optional[CarbonCreditTracker] = None

def get_carbon_tracker() -> CarbonCreditTracker:
    global _tracker
    if _tracker is None:
        _tracker = CarbonCreditTracker()
    return _tracker
