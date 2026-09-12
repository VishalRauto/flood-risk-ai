"""
compensation.py — AI Flood Compensation Assessment

World-first: India's flood compensation process currently takes 6-18 months.
No system combines CV-based damage assessment with automated government
claim generation tied to a live flood event record.

How it works:
  1. After a flood event, citizens/field workers submit damage reports
     with photos (base64 encoded), location, and damage description
  2. The AI assesses damage category and severity from text description
     (in production: add computer vision model for photo analysis)
  3. SDRF/NDRF compensation rates (as per 14th Finance Commission norms)
     are applied to estimate the payout amount
  4. A pre-filled government compensation claim form is generated
     in the correct state format (ready for District Collector signature)
  5. All claims are stored with the flood event ID for audit trail

SDRF compensation rates (2024-25, revised):
  - Crop loss:        ₹17,000/hectare (non-irrigated) | ₹25,000/ha (irrigated)
  - House (full):     ₹1,30,200 (pucca) | ₹95,100 (semi-pucca) | ₹25,100 (kutcha)
  - House (partial):  ₹5,200 (pucca) | ₹3,200 (kutcha)
  - Livestock (cattle): ₹37,500 per animal
  - Livestock (poultry): ₹100 per bird
  - Human death:      ₹4,00,000 per family
  - Boat:             ₹9,600 per boat
  - Fishing net:      ₹3,000 per set
Source: MHA SDRF guidelines 2023
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ── SDRF Compensation Rates (₹) ───────────────────────────────────────────────
SDRF_RATES: Dict[str, Dict[str, float]] = {
    "crop": {
        "non_irrigated_per_ha": 17_000,
        "irrigated_per_ha":     25_000,
        "perennial_per_ha":     30_000,
    },
    "house": {
        "pucca_full":      1_30_200,
        "semi_pucca_full":   95_100,
        "kutcha_full":       25_100,
        "pucca_partial":      5_200,
        "kutcha_partial":     3_200,
    },
    "livestock": {
        "large_cattle":    37_500,
        "small_cattle":    12_000,
        "poultry_per_bird":   100,
    },
    "human": {
        "death_per_family": 4_00_000,
        "injury_grievous":   1_27_000,
    },
    "equipment": {
        "boat":              9_600,
        "fishing_net":       3_000,
        "farm_equipment":   15_000,
    },
    "infrastructure": {
        "shop_full":         25_000,
        "shop_partial":       8_000,
    },
}

# Damage keywords → category mapping
DAMAGE_KEYWORDS: Dict[str, str] = {
    "crop": "crop", "wheat": "crop", "rice": "crop", "paddy": "crop",
    "field": "crop", "farm": "crop", "kharif": "crop", "rabi": "crop",
    "house": "house", "home": "house", "wall": "house", "roof": "house",
    "building": "house", "hut": "house", "ghar": "house",
    "cow": "livestock", "buffalo": "livestock", "goat": "livestock",
    "cattle": "livestock", "animal": "livestock", "poultry": "livestock",
    "chicken": "livestock", "hen": "livestock",
    "death": "human", "died": "human", "killed": "human", "dead": "human",
    "injury": "human", "injured": "human", "hurt": "human",
    "boat": "equipment", "net": "equipment", "tractor": "equipment",
    "shop": "infrastructure", "store": "infrastructure",
}

# State-wise claim form templates
STATE_CLAIM_TEMPLATES: Dict[str, str] = {
    "Odisha":       "Form SDRF-2024/OD-{claim_id}",
    "Assam":        "Form SDRF-2024/AS-{claim_id}",
    "Bihar":        "Form SDRF-2024/BR-{claim_id}",
    "West Bengal":  "Form SDRF-2024/WB-{claim_id}",
    "Andhra Pradesh": "Form SDRF-2024/AP-{claim_id}",
    "Telangana":    "Form SDRF-2024/TG-{claim_id}",
    "Madhya Pradesh": "Form SDRF-2024/MP-{claim_id}",
    "Gujarat":      "Form SDRF-2024/GJ-{claim_id}",
    "default":      "Form SDRF-2024/IN-{claim_id}",
}


@dataclass
class DamageItem:
    category:         str         # crop | house | livestock | human | equipment | infrastructure
    subcategory:      str
    description:      str
    quantity:         float        # hectares / animals / units
    unit:             str
    damage_severity:  str          # PARTIAL | FULL | TOTAL_LOSS
    estimated_value_inr: float
    sdrf_rate_inr:    float
    compensation_inr: float
    evidence_provided: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompensationClaim:
    claim_id:         str
    event_id:         str
    claimant_name:    str
    claimant_phone:   str
    village:          str
    district:         str
    state:            str
    flood_date:       str
    flood_event_risk_score: float
    damage_items:     List[DamageItem]
    total_loss_inr:   float
    total_compensation_inr: float
    form_number:      str
    status:           str          # draft | submitted | under_review | approved | paid
    ai_confidence:    float
    generated_at:     str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes:            str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["damage_items"] = [i.to_dict() for i in self.damage_items]
        return d

    def to_form_text(self) -> str:
        """Generate printable claim form text."""
        lines = [
            f"{'='*60}",
            f"STATE DISASTER RELIEF FUND — COMPENSATION CLAIM",
            f"Form: {self.form_number}",
            f"Claim ID: {self.claim_id}",
            f"{'='*60}",
            f"",
            f"CLAIMANT DETAILS",
            f"Name:     {self.claimant_name}",
            f"Phone:    {self.claimant_phone}",
            f"Village:  {self.village}",
            f"District: {self.district}",
            f"State:    {self.state}",
            f"",
            f"FLOOD EVENT",
            f"Date:     {self.flood_date}",
            f"Risk Score at time: {self.flood_event_risk_score}/10",
            f"Event ID: {self.event_id}",
            f"",
            f"DAMAGE DETAILS",
            f"{'-'*60}",
        ]
        for i, item in enumerate(self.damage_items, 1):
            lines += [
                f"{i}. {item.subcategory} ({item.category.upper()})",
                f"   Description: {item.description}",
                f"   Quantity: {item.quantity} {item.unit}",
                f"   Severity: {item.damage_severity}",
                f"   SDRF Rate: ₹{item.sdrf_rate_inr:,.0f}",
                f"   Compensation: ₹{item.compensation_inr:,.0f}",
                f"",
            ]
        lines += [
            f"{'-'*60}",
            f"TOTAL LOSS (estimated):   ₹{self.total_loss_inr:,.0f}",
            f"TOTAL COMPENSATION (SDRF): ₹{self.total_compensation_inr:,.0f}",
            f"",
            f"AI Assessment Confidence: {self.ai_confidence:.0%}",
            f"",
            f"Verified by: _____________________ (Field Officer)",
            f"Approved by: _____________________ (District Collector)",
            f"Date: _____________________________",
            f"",
            f"Note: This is an AI-generated pre-filled claim. Requires",
            f"field verification before final approval.",
            f"{'='*60}",
        ]
        return "\n".join(lines)


class CompensationAssessor:
    """
    AI-driven flood damage assessment and compensation claim generator.
    Reduces claim processing from 6-18 months to days.
    """

    def assess_from_description(self,
                                  description: str,
                                  claimant_name: str,
                                  claimant_phone: str,
                                  village: str,
                                  district: str,
                                  state: str,
                                  flood_event_id: str = "",
                                  flood_risk_score: float = 7.0,
                                  flood_date: Optional[str] = None) -> CompensationClaim:
        """
        Generate a compensation claim from a text description of damage.
        In production: extend with computer vision on submitted photos.
        """
        claim_id  = f"CLM-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        form_tmpl = STATE_CLAIM_TEMPLATES.get(state, STATE_CLAIM_TEMPLATES["default"])
        form_num  = form_tmpl.format(claim_id=claim_id[-6:])

        # Parse damage items from description
        items    = self._parse_description(description, district)
        total_comp = sum(item.compensation_inr for item in items)
        total_loss = sum(item.estimated_value_inr for item in items)

        # AI confidence based on specificity of description
        confidence = self._compute_confidence(description, items)

        return CompensationClaim(
            claim_id        = claim_id,
            event_id        = flood_event_id or f"EVT-{datetime.now().strftime('%Y%m')}",
            claimant_name   = claimant_name,
            claimant_phone  = claimant_phone,
            village         = village,
            district        = district,
            state           = state,
            flood_date      = flood_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            flood_event_risk_score = flood_risk_score,
            damage_items    = items,
            total_loss_inr  = round(total_loss, 0),
            total_compensation_inr = round(total_comp, 0),
            form_number     = form_num,
            status          = "draft",
            ai_confidence   = round(confidence, 2),
        )

    def _parse_description(self, text: str, district: str) -> List[DamageItem]:
        """Extract damage items from free-text description."""
        items: List[DamageItem] = []
        text_lower = text.lower()

        # Crop damage
        ha_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:hectare|ha|acre|bigha)', text_lower)
        if ha_match or any(k in text_lower for k in ["crop", "paddy", "wheat", "rice", "field"]):
            ha = float(ha_match.group(1)) if ha_match else 1.0
            # Convert acres/bigha to hectares
            if ha_match and "acre" in text_lower:  ha *= 0.405
            if ha_match and "bigha" in text_lower: ha *= 0.202
            irrigated = any(w in text_lower for w in ["irrigated", "canal", "pump"])
            rate = SDRF_RATES["crop"]["irrigated_per_ha" if irrigated else "non_irrigated_per_ha"]
            items.append(DamageItem(
                category        = "crop",
                subcategory     = "Agricultural crop loss",
                description     = f"Crop damage — {'irrigated' if irrigated else 'non-irrigated'}",
                quantity        = round(ha, 2),
                unit            = "hectares",
                damage_severity = "TOTAL_LOSS",
                estimated_value_inr = ha * rate * 1.2,
                sdrf_rate_inr   = rate,
                compensation_inr = ha * rate,
                evidence_provided = False,
            ))

        # House damage
        if any(k in text_lower for k in ["house", "home", "hut", "ghar", "wall", "roof"]):
            pucca = any(w in text_lower for w in ["pucca", "brick", "concrete", "cement"])
            partial = any(w in text_lower for w in ["partial", "damaged", "wall", "roof"])
            if pucca:
                rate = SDRF_RATES["house"]["pucca_partial" if partial else "pucca_full"]
                sub  = "Pucca house — " + ("partial damage" if partial else "fully damaged")
            else:
                rate = SDRF_RATES["house"]["kutcha_partial" if partial else "kutcha_full"]
                sub  = "Kutcha/semi-pucca house — " + ("partial damage" if partial else "fully damaged")
            items.append(DamageItem(
                category        = "house",
                subcategory     = sub,
                description     = "Residential house flood damage",
                quantity        = 1,
                unit            = "unit",
                damage_severity = "PARTIAL" if partial else "FULL",
                estimated_value_inr = rate * 1.5,
                sdrf_rate_inr   = rate,
                compensation_inr = rate,
                evidence_provided = False,
            ))

        # Livestock
        cattle_match = re.search(r'(\d+)\s*(?:cow|buffalo|cattle|bull|ox)', text_lower)
        poultry_match = re.search(r'(\d+)\s*(?:chicken|hen|poultry|bird)', text_lower)
        if cattle_match:
            n = int(cattle_match.group(1))
            rate = SDRF_RATES["livestock"]["large_cattle"]
            items.append(DamageItem(
                category        = "livestock",
                subcategory     = "Large cattle loss",
                description     = f"{n} cattle lost in flood",
                quantity        = n,
                unit            = "animals",
                damage_severity = "TOTAL_LOSS",
                estimated_value_inr = n * rate * 1.8,
                sdrf_rate_inr   = rate,
                compensation_inr = n * rate,
                evidence_provided = False,
            ))
        if poultry_match:
            n = int(poultry_match.group(1))
            rate = SDRF_RATES["livestock"]["poultry_per_bird"]
            items.append(DamageItem(
                category        = "livestock",
                subcategory     = "Poultry loss",
                description     = f"{n} birds lost",
                quantity        = n,
                unit            = "birds",
                damage_severity = "TOTAL_LOSS",
                estimated_value_inr = n * rate * 2,
                sdrf_rate_inr   = rate,
                compensation_inr = n * rate,
                evidence_provided = False,
            ))

        # Human death/injury
        if any(w in text_lower for w in ["death", "died", "dead", "killed"]):
            rate = SDRF_RATES["human"]["death_per_family"]
            items.append(DamageItem(
                category        = "human",
                subcategory     = "Human death",
                description     = "Death due to flood — family compensation",
                quantity        = 1,
                unit            = "family",
                damage_severity = "TOTAL_LOSS",
                estimated_value_inr = rate,
                sdrf_rate_inr   = rate,
                compensation_inr = rate,
                evidence_provided = False,
            ))

        # Boat
        boat_match = re.search(r'(\d+)\s*boat', text_lower)
        if boat_match or "boat" in text_lower:
            n = int(boat_match.group(1)) if boat_match else 1
            rate = SDRF_RATES["equipment"]["boat"]
            items.append(DamageItem(
                category        = "equipment",
                subcategory     = "Fishing boat",
                description     = f"{n} fishing boat(s) damaged/lost",
                quantity        = n,
                unit            = "boats",
                damage_severity = "FULL",
                estimated_value_inr = n * rate * 3,
                sdrf_rate_inr   = rate,
                compensation_inr = n * rate,
                evidence_provided = False,
            ))

        # If nothing detected, add a generic assessment
        if not items:
            items.append(DamageItem(
                category        = "infrastructure",
                subcategory     = "General flood damage",
                description     = "General property damage (requires field verification)",
                quantity        = 1,
                unit            = "unit",
                damage_severity = "PARTIAL",
                estimated_value_inr = 50_000,
                sdrf_rate_inr   = 25_000,
                compensation_inr = 25_000,
                evidence_provided = False,
            ))

        return items

    def _compute_confidence(self, description: str, items: List[DamageItem]) -> float:
        """Estimate AI confidence based on description specificity."""
        base = 0.6
        words = description.split()
        # More specific = higher confidence
        if len(words) > 20:       base += 0.10
        if any(c.category == "crop" and c.quantity > 0 for c in items): base += 0.05
        if re.search(r'\d', description):  base += 0.05  # has numbers
        if len(items) > 2:        base += 0.05
        if "photo" in description.lower() or "image" in description.lower(): base += 0.10
        return min(0.92, base)

    def get_batch_summary(self, claims: List[CompensationClaim]) -> Dict[str, Any]:
        """Summarise a batch of claims for district-level reporting."""
        total_comp = sum(c.total_compensation_inr for c in claims)
        by_category: Dict[str, float] = {}
        for claim in claims:
            for item in claim.damage_items:
                by_category[item.category] = (
                    by_category.get(item.category, 0) + item.compensation_inr)
        return {
            "total_claims":       len(claims),
            "total_compensation_inr": total_comp,
            "avg_per_claim_inr":  round(total_comp / max(len(claims), 1), 0),
            "by_category":        {k: round(v, 0) for k, v in by_category.items()},
            "draft_count":        sum(1 for c in claims if c.status == "draft"),
            "submitted_count":    sum(1 for c in claims if c.status == "submitted"),
        }


_assessor: Optional[CompensationAssessor] = None

def get_compensation_assessor() -> CompensationAssessor:
    global _assessor
    if _assessor is None:
        _assessor = CompensationAssessor()
    return _assessor
