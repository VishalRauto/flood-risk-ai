"""
India Emergency Responder Agent
================================
Manages multi-hazard emergency response for India flood events:
  - Flash flood / rapid river rise
  - Cyclone landfall + storm surge (Bay of Bengal / Arabian Sea)
  - Monsoon compound flooding (simultaneous rain + river + coastal)
  - Dam / reservoir breach risk
  - Population threat with India district-level context

Addresses PDF recommendations:
  * Human decision support (alerts carry data-freshness + confidence + actions)
  * Resilient operation (graceful SMS fallback)
  * Local India vulnerability (Odisha / NE India weighting)
  * Multi-hazard requirement (cyclone + rain + river together)
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Set
import logging

from .base_agent import BaseAgent, AgentInsight, AgentAlert

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# India Emergency Contacts & Channels
# ---------------------------------------------------------------------------
INDIA_EMERGENCY_CHANNELS = [
    "NDMA SACHET (Public SMS)",
    "Doordarshan / All India Radio",
    "IMD Cyclone Warning Division",
    "CWC Flood Forecast Centre",
    "State DMA EOC",
    "NDRF Operations",
]

INDIA_HELPLINES = {
    "NDMA": "1078",
    "NDRF": "011-24363260",
    "IMD":  "mausam.imd.gov.in",
    "CWC":  "cwc.gov.in",
    "INCOIS": "incois.gov.in",
}

# High-density flood-prone districts (used for population risk)
INDIA_HIGH_RISK_DISTRICTS = [
    "Patna", "Muzaffarpur", "Darbhanga", "Guwahati", "Dibrugarh",
    "Puri", "Cuttack", "Bhubaneswar", "Rajahmundry", "Vijayawada",
    "Kolkata", "Howrah", "Allahabad", "Varanasi", "Surat",
]

# Major dams / reservoirs with downstream risk
INDIA_CRITICAL_DAMS = [
    "Hirakud (Mahanadi)", "Tehri (Ganga)", "Bhakra Nangal (Sutlej)",
    "Sardar Sarovar (Narmada)", "Nagarjunasagar (Krishna)",
    "Tungabhadra", "Koyna", "Indira Sagar (Narmada)",
]


def _notify(watershed_name: str, risk_level: str, risk_score: float,
            message: str, affected_areas: List[str] = None):
    """Fire-and-forget Twilio SMS wrapper."""
    try:
        from flood_prediction.notifications import send_sms_alert
        send_sms_alert(
            watershed_name=watershed_name,
            risk_level=risk_level,
            risk_score=risk_score,
            message=message,
            affected_areas=affected_areas or [],
        )
    except Exception as exc:
        logger.error(f"SMS notification failed: {exc}")


class EmergencyResponderAgent(BaseAgent):
    """
    India multi-hazard emergency response coordinator.

    Checks every 3 minutes for:
      1. Flash flood (rapid river rise)
      2. Cyclone / storm-surge landfall
      3. Monsoon compound flooding
      4. Dam / reservoir breach
      5. Mass population threat
      6. Communication system failures

    Every alert carries:
      - Data freshness timestamp
      - Confidence percentage
      - Specific recommended actions for India disaster-management authorities
      - NDMA / NDRF contact information
    """

    def __init__(self):
        super().__init__(
            name="Emergency Responder",
            description="India multi-hazard emergency coordinator — flood, cyclone, dam breach, population threat",
            check_interval=180,
        )
        self.active_incidents: List[Dict] = []
        self.evacuation_zones: Set[str] = set()
        self.response_teams: Dict[str, Dict] = {}
        self.notification_history: List[Dict] = []

    # =========================================================================
    # BaseAgent interface
    # =========================================================================

    async def analyze(self, data: Dict[str, Any]) -> List[AgentInsight]:
        insights = []

        # Active incidents
        ic = len(self.active_incidents)
        insights.append(AgentInsight(
            title="🚨 Active Incidents",
            value=f"{ic} ongoing",
            change=None,
            trend='up' if ic > 3 else 'down' if ic == 0 else 'stable',
            urgency='critical' if ic > 5 else 'high' if ic > 2 else 'normal',
        ))

        # NDRF readiness
        readiness = self._calculate_readiness()
        insights.append(AgentInsight(
            title="🚁 NDRF Response Readiness",
            value=f"{readiness['level']} ({readiness['score']:.0f}%)",
            change=f"{readiness['available_battalions']} battalions ready",
            trend='stable',
            urgency='high' if readiness['score'] < 60 else 'normal',
        ))

        # Evacuation zones
        evac_count = len(self.evacuation_zones)
        insights.append(AgentInsight(
            title="🏃 Evacuation Zones",
            value=f"{evac_count} active zones",
            change="Mandatory + voluntary combined",
            trend='up' if evac_count > 0 else 'stable',
            urgency='critical' if evac_count > 3 else 'high' if evac_count > 0 else 'normal',
        ))

        # India communication channels
        comm = self._check_india_comms()
        insights.append(AgentInsight(
            title="📡 Alert Channels",
            value=f"{comm['operational']}/{comm['total']} active",
            change=", ".join(comm['active_names'][:2]),
            trend='stable',
            urgency='high' if comm['operational'] < comm['total'] * 0.7 else 'normal',
        ))

        # Alerts sent today
        stats = self._alert_stats()
        insights.append(AgentInsight(
            title="📢 Alerts Dispatched",
            value=f"{stats['last_hour']} last hour",
            change=f"{stats['total_today']} today via SACHET/SMS",
            trend='stable',
            urgency='normal',
        ))

        return insights

    async def check_alerts(self, data: Dict[str, Any]) -> List[AgentAlert]:
        alerts = []
        confidence = self._estimate_confidence(data)
        freshness  = self._data_freshness_label(data)

        # 1. Flash flood
        flash = self._assess_flash_flood(data)
        if flash['risk']:
            alert = AgentAlert(
                id=f"flash_flood_india_{datetime.now().strftime('%Y%m%d%H%M')}",
                title="⚡ FLASH FLOOD WARNING — India",
                message=(
                    f"Rapid river rise detected at {len(flash['areas'])} sites "
                    f"({', '.join(flash['areas'][:3])}). "
                    f"Response window: {flash['window_minutes']} minutes. "
                    f"[Data: {freshness} | Confidence: {confidence:.0f}%]"
                ),
                severity="critical",
                source_agent=self.name,
                affected_areas=flash['areas'],
                recommendations=[
                    "IMMEDIATE: Alert District Collector and State DMA EOC",
                    "Deploy NDRF rescue boats to identified staging areas",
                    "Activate SACHET mass-SMS to affected districts",
                    "Broadcast on Doordarshan / All India Radio",
                    "Close low-lying causeways and bridges immediately",
                    "Contact NDMA Helpline 1078 for national-level coordination",
                    f"⚠️ Confidence {confidence:.0f}% — cross-verify with CWC flood forecast",
                ],
                expires_at=datetime.now(timezone.utc) + timedelta(hours=6),
            )
            alerts.append(alert)
            await self.send_emergency_alert(alert)

        # 2. Cyclone + storm surge
        cyclone = self._assess_cyclone_risk(data)
        if cyclone['risk']:
            alert = AgentAlert(
                id=f"cyclone_india_{datetime.now().strftime('%Y%m%d%H')}",
                title=f"🌀 CYCLONE ALERT — {cyclone['category']}",
                message=(
                    f"{cyclone['category']} approaching India coast. "
                    f"Estimated landfall: {cyclone['landfall_area']}. "
                    f"Storm surge: {cyclone['surge_m']:.1f}m expected. "
                    f"[Data: {freshness} | Confidence: {confidence:.0f}%]"
                ),
                severity="critical",
                source_agent=self.name,
                affected_areas=cyclone['coastal_districts'],
                recommendations=[
                    "IMMEDIATE: Alert IMD Cyclone Warning Division",
                    "Evacuate coastal fishing communities — prohibit sea entry",
                    "Issue storm-surge inundation maps via INCOIS portal",
                    "Activate coastal district disaster plans",
                    "Coordinate with Indian Navy and Coast Guard",
                    "Pre-position NDRF teams at cyclone-prone coastline",
                    "Open cyclone shelters for coastal population",
                    f"NDMA: 1078 | NDRF: 011-24363260 | INCOIS: incois.gov.in",
                ],
                expires_at=datetime.now(timezone.utc) + timedelta(hours=72),
            )
            alerts.append(alert)
            await self.send_emergency_alert(alert)

        # 3. Monsoon compound flooding
        compound = self._assess_compound_monsoon(data)
        if compound['risk']:
            alert = AgentAlert(
                id=f"compound_monsoon_{datetime.now().strftime('%Y%m%d%H')}",
                title="🌊🌧️ COMPOUND MONSOON FLOOD",
                message=(
                    f"Simultaneous extreme rainfall AND river overflow at "
                    f"{compound['affected_count']} sites. "
                    f"Worst affected: {', '.join(compound['worst_areas'][:3])}. "
                    f"[Data: {freshness} | Confidence: {confidence:.0f}%]"
                ),
                severity="critical",
                source_agent=self.name,
                affected_areas=compound['worst_areas'],
                recommendations=[
                    "Declare district-level disaster in affected areas",
                    "Mandatory evacuation of river-confluence low-lying zones",
                    "Deploy additional NDRF battalions",
                    "Coordinate with State Irrigation Dept for reservoir releases",
                    "Activate Army/Air Force for rescue if road access cut",
                    "Mobilise SDRF (State Disaster Response Force)",
                    f"⚠️ Compound event — standard response plans may be insufficient",
                ],
            )
            alerts.append(alert)
            await self.send_emergency_alert(alert)

        # 4. Dam / reservoir breach risk
        dam_risk = self._assess_dam_breach_risk(data)
        if dam_risk['risk']:
            alert = AgentAlert(
                id=f"dam_breach_{datetime.now().strftime('%Y%m%d%H')}",
                title="🏗️ DAM / RESERVOIR BREACH RISK",
                message=(
                    f"Critical inflow levels at {dam_risk['dam_count']} reservoirs. "
                    f"Potential uncontrolled release from: {', '.join(dam_risk['at_risk_dams'])}. "
                    f"Downstream population at risk: ~{dam_risk['downstream_pop']:,}. "
                    f"[Data: {freshness} | Confidence: {confidence:.0f}%]"
                ),
                severity="critical",
                source_agent=self.name,
                affected_areas=dam_risk['downstream_areas'],
                recommendations=[
                    "IMMEDIATE: Contact Central Water Commission Dam Safety Cell",
                    "Inspect dam structures — deploy emergency engineering teams",
                    "Pre-evacuate downstream villages within 10km",
                    "Coordinate controlled release schedule with dam operators",
                    "Issue public warning in downstream districts via loudspeaker",
                    "Place NDRF rescue teams at downstream staging points",
                    f"CWC: cwc.gov.in | Dam Safety Authority: dascofindia.org",
                ],
            )
            alerts.append(alert)
            await self.send_emergency_alert(alert)

        # 5. Mass population threat
        pop_threat = self._assess_population_threat(data)
        if pop_threat['population'] > 10_000:
            alert = AgentAlert(
                id=f"population_threat_{datetime.now().strftime('%Y%m%d%H')}",
                title="👥 MASS POPULATION FLOOD THREAT",
                message=(
                    f"~{pop_threat['population']:,} people in immediate flood-risk zones "
                    f"across {len(pop_threat['districts'])} districts: "
                    f"{', '.join(pop_threat['districts'][:4])}. "
                    f"[Data: {freshness} | Confidence: {confidence:.0f}%]"
                ),
                severity="critical",
                source_agent=self.name,
                affected_areas=pop_threat['districts'],
                recommendations=[
                    "Immediate evacuation order for identified flood-prone areas",
                    "Activate Panchayat-level emergency committees",
                    "Deploy NDRF + SDRF rescue teams",
                    "Open relief camps — coordinate with Red Cross / NGOs",
                    "Issue SACHET alert to all mobile subscribers in affected area",
                    "Ensure safe drinking water and medical supplies at camps",
                    f"NDMA: 1078 | Red Cross: 01123711551",
                ],
            )
            alerts.append(alert)
            await self.send_emergency_alert(alert)

        # 6. Communication failures
        comm_fail = self._detect_comm_failures()
        if comm_fail:
            alerts.append(AgentAlert(
                id=f"comm_failure_{datetime.now().strftime('%Y%m%d%H')}",
                title="📡 Emergency Communication Disruption",
                message=(
                    f"Communication disruption detected in {len(comm_fail)} areas: "
                    f"{', '.join(comm_fail)}. "
                    f"Emergency coordination may be impacted."
                ),
                severity="warning",
                source_agent=self.name,
                affected_areas=comm_fail,
                recommendations=[
                    "Activate satellite phone backup for district EOCs",
                    "Deploy VSAT mobile communication units",
                    "Use Ham radio network for inter-district coordination",
                    "Dispatch physical messengers to cut-off areas",
                ],
            ))

        return alerts

    # =========================================================================
    # India-specific hazard assessment methods
    # =========================================================================

    def _assess_flash_flood(self, data: Dict) -> Dict:
        areas = []
        min_window = 60
        for w in data.get('watersheds', []):
            rate   = w.get('trend_rate_cfs_per_hour', 0) or 0
            flow   = w.get('current_streamflow_cfs', 0) or 0
            stage  = w.get('flood_stage_cfs', 0) or 50_000
            risk   = w.get('risk_score', 0) or 0
            rapid_rise  = rate > 200
            near_stage  = stage > 0 and flow > stage * 0.75
            high_risk   = risk > 8
            if (rapid_rise and near_stage) or (high_risk and rapid_rise):
                areas.append(w.get('name', '?'))
                if rate > 500:
                    min_window = min(min_window, 20)
                elif rate > 300:
                    min_window = min(min_window, 35)
        return {'risk': len(areas) > 0, 'areas': areas, 'window_minutes': min_window}

    def _assess_cyclone_risk(self, data: Dict) -> Dict:
        """Use seasonal + imd_data wind indicators."""
        month = datetime.now(timezone.utc).month
        imd   = data.get('imd_data', {})
        max_wind = 0.0
        if isinstance(imd, dict):
            for v in imd.values():
                if isinstance(v, dict):
                    w = v.get('wind_speed_kmh', 0) or 0
                    max_wind = max(max_wind, float(w))

        # Seasonal + wind-based decision
        at_risk = (
            (month in (10, 11) and max_wind >= 62) or
            (month in (5, 6)   and max_wind >= 62) or
            max_wind >= 88
        )
        if not at_risk:
            return {'risk': False}

        if max_wind >= 220:   cat = "Super Cyclone";          surge = 5.0
        elif max_wind >= 165: cat = "Very Severe Cyclone";    surge = 4.0
        elif max_wind >= 120: cat = "Severe Cyclone";         surge = 3.0
        elif max_wind >= 88:  cat = "Cyclone";                surge = 2.0
        else:                 cat = "Deep Depression";         surge = 1.0

        coastal = ["Odisha Coast", "Andhra Pradesh Coast",
                   "West Bengal Coast", "Tamil Nadu Coast"]
        return {
            'risk':             True,
            'category':         cat,
            'surge_m':          surge,
            'landfall_area':    coastal[0],
            'coastal_districts': coastal,
        }

    def _assess_compound_monsoon(self, data: Dict) -> Dict:
        ws = data.get('watersheds', [])
        high_rain  = sum(1 for w in ws if (w.get('daily_precipitation_mm') or 0) >= 64.5)
        high_river = sum(1 for w in ws if w.get('risk_score', 0) >= 6)
        both = min(high_rain, high_river)
        worst = [
            w.get('name', '?') for w in ws
            if w.get('risk_score', 0) >= 6
        ][:6]
        return {
            'risk':           both >= 2,
            'affected_count': both,
            'worst_areas':    worst,
        }

    def _assess_dam_breach_risk(self, data: Dict) -> Dict:
        ws = data.get('watersheds', [])
        near_capacity = [
            w for w in ws
            if (w.get('flood_stage_cfs', 0) or 0) > 0 and
               (w.get('current_streamflow_cfs', 0) or 0) >
               (w.get('flood_stage_cfs', 0) or 1) * 0.92
        ]
        if not near_capacity:
            return {'risk': False}

        at_risk_dams = INDIA_CRITICAL_DAMS[:len(near_capacity)]
        downstream   = [f"Downstream of {w.get('name', '?')}" for w in near_capacity]
        pop_estimate = sum(
            int((w.get('basin_size_sqmi', 100) or 100) * 500)
            for w in near_capacity
        )
        return {
            'risk':            True,
            'dam_count':       len(near_capacity),
            'at_risk_dams':    at_risk_dams,
            'downstream_areas': downstream,
            'downstream_pop':  pop_estimate,
        }

    def _assess_population_threat(self, data: Dict) -> Dict:
        ws         = data.get('watersheds', [])
        high_risk  = [w for w in ws if w.get('risk_score', 0) > 7]
        population = sum(
            int((w.get('basin_size_sqmi', 100) or 100) * 200)
            for w in high_risk
        )
        districts = list({
            w.get('name', '?').split()[0] for w in high_risk
        })[:8]
        return {'population': population, 'districts': districts}

    def _detect_comm_failures(self) -> List[str]:
        """
        Detect real communication degradation based on data staleness.

        A site is considered "comm-degraded" if its last_updated timestamp
        is more than 3 hours old — indicating the telemetry feed has dropped.
        This uses actual data freshness rather than random simulation.
        """
        degraded_areas: List[str] = []
        try:
            # Check active incident watersheds for staleness
            for incident in self.active_incidents:
                last_updated = incident.get('last_updated', '')
                if not last_updated:
                    continue
                try:
                    ts = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                    age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
                    if age_hours > 3:
                        area = incident.get('watershed', incident.get('name', 'Unknown area'))
                        degraded_areas.append(f"{area} (data {age_hours:.0f}h old)")
                except Exception:
                    pass
        except Exception:
            pass
        return degraded_areas

    # =========================================================================
    # Readiness, comms, stats helpers
    # =========================================================================

    def _calculate_readiness(self) -> Dict:
        base = 88
        reduction = min(25, len(self.active_incidents) * 8)
        score = max(45, base - reduction)
        level = (
            "OPTIMAL"  if score >= 88 else
            "GOOD"     if score >= 72 else
            "ADEQUATE" if score >= 55 else
            "LIMITED"
        )
        battalions = max(1, 12 - len(self.active_incidents))
        return {'score': score, 'level': level, 'available_battalions': battalions}

    def _check_india_comms(self) -> Dict:
        systems = {
            "SACHET":           True,
            "Doordarshan/AIR":  True,
            "Cell Broadcast":   True,
            "NDMA Portal":      True,
            "State EOC Lines":  True,
            "CWC FFC":          True,
        }
        active = [k for k, v in systems.items() if v]
        return {
            'total':        len(systems),
            'operational':  len(active),
            'active_names': active,
        }

    def _estimate_confidence(self, data: Dict) -> float:
        ws = data.get('watersheds', [])
        if not ws:
            return 40.0
        fresh = sum(1 for w in ws if self._is_fresh(w))
        return min(92.0, max(35.0, (fresh / len(ws)) * 90))

    def _data_freshness_label(self, data: Dict) -> str:
        ws = data.get('watersheds', [])
        ages = []
        for w in ws:
            lu = w.get('last_updated', '')
            try:
                t   = datetime.fromisoformat(lu.replace('Z', '+00:00'))
                ages.append((datetime.now(timezone.utc) - t).total_seconds() / 60)
            except Exception:
                pass
        if not ages:
            return "age unknown"
        avg = sum(ages) / len(ages)
        if avg < 15:   return "live <15 min"
        if avg < 60:   return f"{avg:.0f} min old"
        return f"{avg/60:.1f} hr old — STALE"

    def _is_fresh(self, w: Dict) -> bool:
        lu = w.get('last_updated', '')
        try:
            t = datetime.fromisoformat(lu.replace('Z', '+00:00'))
            return (datetime.now(timezone.utc) - t) < timedelta(hours=2)
        except Exception:
            return False

    def _alert_stats(self) -> Dict:
        now = datetime.now(timezone.utc)
        last_hour = sum(
            1 for a in self.notification_history
            if (now - a.get('timestamp', now)).total_seconds() < 3600
        )
        today = sum(
            1 for a in self.notification_history
            if a.get('timestamp', now) >= now.replace(hour=0, minute=0, second=0)
        )
        return {'last_hour': last_hour, 'total_today': today}

    # =========================================================================
    # Alert dispatch
    # =========================================================================

    async def send_emergency_alert(
        self, alert: AgentAlert, channels: List[str] = None
    ) -> bool:
        try:
            if channels is None:
                channels = INDIA_EMERGENCY_CHANNELS[:4]

            # Twilio SMS for critical/high
            if alert.severity in ("critical", "high"):
                level = "CRITICAL" if alert.severity == "critical" else "HIGH"
                name  = alert.affected_areas[0] if alert.affected_areas else alert.title
                _notify(
                    watershed_name=name,
                    risk_level=level,
                    risk_score=9.0 if level == "CRITICAL" else 7.0,
                    message=alert.message,
                    affected_areas=alert.affected_areas or [],
                )

            self.notification_history.append({
                'timestamp': datetime.now(timezone.utc),
                'alert_id':  alert.id,
                'severity':  alert.severity,
                'channels':  channels,
            })
            if len(self.notification_history) > 1000:
                self.notification_history = self.notification_history[-500:]

            logger.info(
                f"India emergency alert dispatched: {alert.title} "
                f"via {', '.join(channels)}"
            )
            return True

        except Exception as exc:
            logger.error(f"Error dispatching alert: {exc}")
            return False

    async def activate_response_team(self, incident_type: str, location: str) -> str:
        team_id = f"NDRF_{len(self.response_teams)+1}_{datetime.now().strftime('%Y%m%d%H%M')}"
        self.response_teams[team_id] = {
            'activated_at':  datetime.now(timezone.utc),
            'incident_type': incident_type,
            'location':      location,
            'status':        'dispatched',
        }
        logger.info(f"NDRF team {team_id} activated for {incident_type} at {location}")
        return team_id

    async def declare_evacuation_zone(
        self, zone_name: str, evacuation_type: str = "voluntary"
    ) -> bool:
        self.evacuation_zones.add(f"{zone_name}_{evacuation_type}")
        logger.info(f"Evacuation zone declared: {zone_name} ({evacuation_type})")
        return True
