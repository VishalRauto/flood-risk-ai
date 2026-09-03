"""
Data source integrations for India Flood Prediction.
Uses Open-Meteo (free, global) for river discharge and weather data.
India Water Resources Information System (WRIS) data is referenced for river basins.
"""

import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json
from . import db
from .settings import settings

log = logging.getLogger(__name__)


@dataclass
class StreamflowData:
    """Streamflow / discharge data"""
    site_code: str
    site_name: str
    streamflow_cfs: float       # stored as cumecs (m³/s) × 35.315 for compatibility
    gage_height_ft: Optional[float]
    timestamp: datetime
    quality_code: str = "P"     # P=Provisional (Open-Meteo), A=Approved


@dataclass
class RiverSite:
    """India river monitoring site"""
    site_code: str
    site_name: str
    latitude: float
    longitude: float
    state: str
    district: str
    drainage_area_sqkm: Optional[float] = None


# =============================================================================
# Regional Configuration — India
# =============================================================================

REGION_CONFIG = {
    "IN-GANGA": {
        "name": "Ganga Basin",
        "code": "IN-GANGA",
        "description": "Ganga river basin — Uttarakhand, UP, Bihar, West Bengal",
        "center_lat": 26.0,
        "center_lng": 82.0,
        "zoom": 6,
        "state_codes": ["UK", "UP", "BR", "WB"],
        "sites": [
            "ganga_haridwar", "ganga_allahabad", "ganga_varanasi",
            "ganga_patna", "yamuna_delhi", "yamuna_agra",
            "ghaghra_ayodhya", "sone_arrah", "gandak_gandak_nagar"
        ]
    },
    "IN-BRAHMAPUTRA": {
        "name": "Brahmaputra Basin",
        "code": "IN-BRAHMAPUTRA",
        "description": "Brahmaputra river basin — Assam and Arunachal Pradesh",
        "center_lat": 26.5,
        "center_lng": 93.0,
        "zoom": 6,
        "state_codes": ["AS", "AR"],
        "sites": [
            "brahmaputra_guwahati", "brahmaputra_dibrugarh",
            "subansiri_north_lakhimpur", "barak_silchar",
            "kopili_kampur", "manas_beki"
        ]
    },
    "IN-MAHANADI": {
        "name": "Mahanadi Basin",
        "code": "IN-MAHANADI",
        "description": "Mahanadi river basin — Chhattisgarh and Odisha",
        "center_lat": 20.5,
        "center_lng": 82.5,
        "zoom": 6,
        "state_codes": ["CT", "OD"],
        "sites": [
            "mahanadi_hirakud", "mahanadi_cuttack",
            "tel_kantamal", "ib_brajrajnagar", "jonk_jonk"
        ]
    },
    "IN-GODAVARI": {
        "name": "Godavari Basin",
        "code": "IN-GODAVARI",
        "description": "Godavari river basin — Maharashtra, Telangana, Andhra Pradesh",
        "center_lat": 18.5,
        "center_lng": 79.5,
        "zoom": 6,
        "state_codes": ["MH", "TG", "AP"],
        "sites": [
            "godavari_nashik", "godavari_rajahmundry",
            "pranhita_pranhita", "indravati_jagdalpur",
            "wardha_arvi", "wainganga_bamni"
        ]
    },
    "IN-KRISHNA": {
        "name": "Krishna Basin",
        "code": "IN-KRISHNA",
        "description": "Krishna river basin — Maharashtra, Karnataka, Andhra Pradesh",
        "center_lat": 16.5,
        "center_lng": 77.0,
        "zoom": 6,
        "state_codes": ["MH", "KA", "AP"],
        "sites": [
            "krishna_sangam", "krishna_vijayawada",
            "tungabhadra_hospet", "bhima_yadgir",
            "ghataprabha_saundatti"
        ]
    },
    "IN-INDUS": {
        "name": "Indus Basin (India)",
        "code": "IN-INDUS",
        "description": "Indus tributaries — Punjab, Himachal Pradesh, J&K",
        "center_lat": 32.0,
        "center_lng": 76.0,
        "zoom": 6,
        "state_codes": ["PB", "HP", "JK"],
        "sites": [
            "sutlej_ropar", "beas_mandi",
            "ravi_madhopur", "chenab_akhnoor", "jhelum_sangam"
        ]
    },
    "IN-NARMADA": {
        "name": "Narmada Basin",
        "code": "IN-NARMADA",
        "description": "Narmada river basin — Madhya Pradesh and Gujarat",
        "center_lat": 22.5,
        "center_lng": 77.5,
        "zoom": 6,
        "state_codes": ["MP", "GJ"],
        "sites": [
            "narmada_jabalpur", "narmada_sardar_sarovar",
            "tawa_itarsi", "bargi_bargi"
        ]
    },
    "IN-KAVERI": {
        "name": "Kaveri Basin",
        "code": "IN-KAVERI",
        "description": "Kaveri river basin — Karnataka and Tamil Nadu",
        "center_lat": 12.5,
        "center_lng": 77.5,
        "zoom": 6,
        "state_codes": ["KA", "TN"],
        "sites": [
            "kaveri_krishnarajasagara", "kaveri_trichy",
            "hemavathi_gorur", "arkavathi_kanakpura",
            "bhavani_bhavani_sagar"
        ]
    }
}

# Site coordinate lookup used by Open-Meteo flood API
INDIA_RIVER_SITES: Dict[str, RiverSite] = {
    # Ganga Basin
    "ganga_haridwar":       RiverSite("ganga_haridwar",       "Ganga at Haridwar",           29.9457,  78.1642, "Uttarakhand", "Haridwar",     25820),
    "ganga_allahabad":      RiverSite("ganga_allahabad",      "Ganga at Prayagraj",           25.4358,  81.8463, "Uttar Pradesh","Prayagraj",   860330),
    "ganga_varanasi":       RiverSite("ganga_varanasi",       "Ganga at Varanasi",            25.3176,  83.0062, "Uttar Pradesh","Varanasi",    920000),
    "ganga_patna":          RiverSite("ganga_patna",          "Ganga at Patna",               25.5941,  85.1376, "Bihar",       "Patna",       1050000),
    "yamuna_delhi":         RiverSite("yamuna_delhi",         "Yamuna at Delhi",              28.6139,  77.2090, "Delhi",       "New Delhi",    341623),
    "yamuna_agra":          RiverSite("yamuna_agra",          "Yamuna at Agra",               27.1767,  78.0081, "Uttar Pradesh","Agra",        365000),
    "ghaghra_ayodhya":      RiverSite("ghaghra_ayodhya",      "Ghaghra at Ayodhya",           26.7922,  82.1998, "Uttar Pradesh","Faizabad",    127600),
    "sone_arrah":           RiverSite("sone_arrah",           "Sone at Arrah",                25.5566,  84.6640, "Bihar",       "Bhojpur",      67500),
    "gandak_gandak_nagar":  RiverSite("gandak_gandak_nagar",  "Gandak at Gandak Nagar",       26.8956,  84.4509, "Bihar",       "Champaran",    46300),
    # Brahmaputra Basin
    "brahmaputra_guwahati": RiverSite("brahmaputra_guwahati", "Brahmaputra at Guwahati",      26.1445,  91.7362, "Assam",       "Kamrup",      583000),
    "brahmaputra_dibrugarh":RiverSite("brahmaputra_dibrugarh","Brahmaputra at Dibrugarh",     27.4728,  94.9120, "Assam",       "Dibrugarh",   194000),
    "subansiri_north_lakhimpur":RiverSite("subansiri_north_lakhimpur","Subansiri at N.Lakhimpur",27.2343, 94.1036,"Assam","Lakhimpur",36900),
    "barak_silchar":        RiverSite("barak_silchar",        "Barak at Silchar",             24.8333,  92.7789, "Assam",       "Cachar",       41723),
    "kopili_kampur":        RiverSite("kopili_kampur",        "Kopili at Kampur",             26.0500,  92.6500, "Assam",       "Nagaon",       10000),
    "manas_beki":           RiverSite("manas_beki",           "Manas at Beki Bridge",         26.5600,  90.9800, "Assam",       "Barpeta",      41350),
    # Mahanadi Basin
    "mahanadi_hirakud":     RiverSite("mahanadi_hirakud",     "Mahanadi at Hirakud Dam",      21.5235,  83.8714, "Odisha",      "Sambalpur",    83400),
    "mahanadi_cuttack":     RiverSite("mahanadi_cuttack",     "Mahanadi at Cuttack",          20.4625,  85.8830, "Odisha",      "Cuttack",     135000),
    "tel_kantamal":         RiverSite("tel_kantamal",         "Tel at Kantamal",              20.6344,  83.7315, "Odisha",      "Boudh",        24870),
    "ib_brajrajnagar":      RiverSite("ib_brajrajnagar",      "Ib at Brajrajnagar",           21.8242,  83.9219, "Odisha",      "Jharsuguda",    6480),
    "jonk_jonk":            RiverSite("jonk_jonk",            "Jonk at Jonk",                 21.2500,  82.3500, "Chhattisgarh","Raipur",        7000),
    # Godavari Basin
    "godavari_nashik":      RiverSite("godavari_nashik",      "Godavari at Nashik",           20.0059,  73.7897, "Maharashtra", "Nashik",        5765),
    "godavari_rajahmundry": RiverSite("godavari_rajahmundry", "Godavari at Rajahmundry",      17.0005,  81.7799, "Andhra Pradesh","East Godavari",312812),
    "pranhita_pranhita":    RiverSite("pranhita_pranhita",    "Pranhita at Pranhita",         18.8600,  79.7300, "Telangana",   "Adilabad",     106460),
    "indravati_jagdalpur":  RiverSite("indravati_jagdalpur",  "Indravati at Jagdalpur",       19.0748,  82.0340, "Chhattisgarh","Bastar",        39759),
    "wardha_arvi":          RiverSite("wardha_arvi",          "Wardha at Arvi",               20.9934,  78.9241, "Maharashtra", "Wardha",        25900),
    "wainganga_bamni":      RiverSite("wainganga_bamni",      "Wainganga at Bamni",           20.7000,  79.9500, "Maharashtra", "Bhandara",     21900),
    # Krishna Basin
    "krishna_sangam":       RiverSite("krishna_sangam",       "Krishna at Sangam",            17.3753,  76.8200, "Karnataka",   "Raichur",      113271),
    "krishna_vijayawada":   RiverSite("krishna_vijayawada",   "Krishna at Vijayawada",        16.5062,  80.6480, "Andhra Pradesh","Krishna",     258948),
    "tungabhadra_hospet":   RiverSite("tungabhadra_hospet",   "Tungabhadra at Hospet",        15.2689,  76.3909, "Karnataka",   "Bellary",       69000),
    "bhima_yadgir":         RiverSite("bhima_yadgir",         "Bhima at Yadgir",              16.7700,  77.1300, "Karnataka",   "Yadgir",        69425),
    "ghataprabha_saundatti":RiverSite("ghataprabha_saundatti","Ghataprabha at Saundatti",     15.7786,  75.1234, "Karnataka",   "Belagavi",      8829),
    # Indus (India portion)
    "sutlej_ropar":         RiverSite("sutlej_ropar",         "Sutlej at Ropar",              30.9645,  76.5266, "Punjab",      "Rupnagar",     54000),
    "beas_mandi":           RiverSite("beas_mandi",           "Beas at Mandi",                31.7096,  76.9321, "Himachal Pradesh","Mandi",      12000),
    "ravi_madhopur":        RiverSite("ravi_madhopur",        "Ravi at Madhopur",             32.2783,  75.6347, "Punjab",      "Pathankot",    14442),
    "chenab_akhnoor":       RiverSite("chenab_akhnoor",       "Chenab at Akhnoor",            32.8800,  74.7300, "J&K",         "Jammu",        28000),
    "jhelum_sangam":        RiverSite("jhelum_sangam",        "Jhelum near Sangam",           33.6400,  74.9900, "J&K",         "Anantnag",     14400),
    # Narmada Basin
    "narmada_jabalpur":     RiverSite("narmada_jabalpur",     "Narmada at Jabalpur",          23.1815,  79.9864, "Madhya Pradesh","Jabalpur",    35156),
    "narmada_sardar_sarovar":RiverSite("narmada_sardar_sarovar","Narmada at Sardar Sarovar",  21.8270,  73.7496, "Gujarat",     "Narmada",      88000),
    "tawa_itarsi":          RiverSite("tawa_itarsi",          "Tawa at Itarsi",               22.6217,  77.7643, "Madhya Pradesh","Hoshangabad",  6037),
    "bargi_bargi":          RiverSite("bargi_bargi",          "Narmada at Bargi Dam",         23.0500,  79.9000, "Madhya Pradesh","Jabalpur",    14100),
    # Kaveri Basin
    "kaveri_krishnarajasagara":RiverSite("kaveri_krishnarajasagara","Kaveri at KRS Dam",      12.4262,  76.5716, "Karnataka",   "Mandya",       25372),
    "kaveri_trichy":        RiverSite("kaveri_trichy",        "Kaveri at Tiruchirappalli",    10.7905,  78.7047, "Tamil Nadu",  "Tiruchirappalli",81155),
    "hemavathi_gorur":      RiverSite("hemavathi_gorur",      "Hemavathi at Gorur Dam",       12.9600,  76.0800, "Karnataka",   "Hassan",        5412),
    "arkavathi_kanakpura":  RiverSite("arkavathi_kanakpura",  "Arkavathi at Kanakpura",       12.5450,  77.4180, "Karnataka",   "Ramanagara",    4188),
    "bhavani_bhavani_sagar":RiverSite("bhavani_bhavani_sagar","Bhavani at Bhavani Sagar",     11.4450,  77.1200, "Tamil Nadu",  "Erode",         6100),
}


class OpenMeteoFloodAPI:
    """
    Fetches river discharge forecasts from Open-Meteo Flood API.
    Free, no API key required, works globally including India.
    https://open-meteo.com/en/docs/flood-api
    """

    BASE_URL = "https://flood-api.open-meteo.com/v1/flood"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'IndiaFloodIntelligence/1.0 (Python requests)'
        })

    def get_discharge_forecast(self, site: RiverSite, days: int = 7) -> Optional[Dict]:
        """
        Get river discharge forecast for a site.
        Returns daily river_discharge in m³/s.
        """
        params = {
            'latitude': site.latitude,
            'longitude': site.longitude,
            'daily': 'river_discharge,river_discharge_mean,river_discharge_median,river_discharge_max,river_discharge_min',
            'forecast_days': days,
            'past_days': 1,
        }
        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            log.error(f"Open-Meteo Flood API error for {site.site_code}: {e}")
            return None

    def get_current_discharge_cumecs(self, site: RiverSite) -> Optional[float]:
        """Get latest discharge estimate in m³/s (cumecs)"""
        data = self.get_discharge_forecast(site, days=1)
        if not data:
            return None
        try:
            values = data.get('daily', {}).get('river_discharge', [])
            if values:
                val = values[-1]
                return float(val) if val is not None else None
        except Exception as e:
            log.warning(f"Could not parse discharge for {site.site_code}: {e}")
        return None

    def get_streamflow_data(self, site_codes: List[str]) -> List[StreamflowData]:
        """Get streamflow data for multiple sites (compatible interface)"""
        results = []
        api = OpenMeteoFloodAPI(self.timeout)
        for code in site_codes:
            site = INDIA_RIVER_SITES.get(code)
            if not site:
                log.warning(f"Unknown site code: {code}")
                continue
            cumecs = api.get_current_discharge_cumecs(site)
            if cumecs is None:
                continue
            # Convert m³/s to CFS (1 m³/s = 35.3147 CFS) for compatibility with existing risk logic
            cfs = cumecs * 35.3147
            results.append(StreamflowData(
                site_code=site.site_code,
                site_name=site.site_name,
                streamflow_cfs=round(cfs, 1),
                gage_height_ft=None,
                timestamp=datetime.now(timezone.utc),
                quality_code='P'
            ))
            log.info(f"Fetched discharge for {site.site_name}: {cumecs:.1f} m³/s ({cfs:.0f} CFS)")
        return results


class IMDWeatherAPI:
    """
    India Meteorological Department compatible weather fetch via Open-Meteo.
    Open-Meteo is free and covers India fully.
    """
    BASE_URL = "https://api.open-meteo.com/v1/forecast"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'IndiaFloodIntelligence/1.0'
        })

    def get_weather(self, lat: float, lon: float) -> Optional[Dict]:
        params = {
            'latitude': lat,
            'longitude': lon,
            'current': 'temperature_2m,relative_humidity_2m,precipitation,rain,weather_code,cloud_cover,wind_speed_10m',
            'hourly': 'precipitation_probability,precipitation,rain,weather_code',
            'daily': 'precipitation_sum,rain_sum,precipitation_probability_max,weather_code,temperature_2m_max,temperature_2m_min',
            'forecast_days': 3,
            'timezone': 'Asia/Kolkata',
            'temperature_unit': 'celsius',
            'precipitation_unit': 'mm',
            'wind_speed_unit': 'kmh'
        }
        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            log.error(f"Open-Meteo weather API error: {e}")
            return None


# =============================================================================
# Helper functions (keep same interface as before)
# =============================================================================

def get_available_regions() -> List[Dict[str, Any]]:
    """Get list of all available India regions"""
    return [
        {
            "code": config["code"],
            "name": config["name"],
            "description": config["description"],
            "center_lat": config["center_lat"],
            "center_lng": config["center_lng"],
            "zoom": config["zoom"],
            "watershed_count": len(config["sites"])
        }
        for code, config in REGION_CONFIG.items()
    ]


def get_region_config(region_code: str) -> Optional[Dict[str, Any]]:
    """Get configuration for a specific India region"""
    return REGION_CONFIG.get(region_code.upper()) or REGION_CONFIG.get(region_code)


def get_major_river_sites_by_region(region_code: str = "IN-GANGA") -> List[str]:
    """Get site codes for the specified India region"""
    config = get_region_config(region_code)
    if config:
        return config["sites"]
    return REGION_CONFIG["IN-GANGA"]["sites"]


def get_major_india_river_sites() -> List[str]:
    """Get key monitoring sites across India (one per major basin)"""
    return [
        "ganga_patna",
        "brahmaputra_guwahati",
        "mahanadi_hirakud",
        "godavari_rajahmundry",
        "krishna_vijayawada",
        "narmada_sardar_sarovar",
        "kaveri_krishnarajasagara",
        "sutlej_ropar",
        "yamuna_delhi",
        "mahanadi_cuttack",
        "godavari_nashik",
        "barak_silchar",
    ]


def calculate_risk_level(streamflow_cfs: float, flood_stage_cfs: Optional[float] = None) -> Tuple[str, float]:
    """
    Calculate flood risk level and score based on streamflow.
    Same interface as before — works with CFS values.
    """
    if flood_stage_cfs and streamflow_cfs >= flood_stage_cfs:
        risk_level = "High"
        risk_score = min(10.0, 7.0 + (streamflow_cfs / flood_stage_cfs - 1.0) * 3.0)
    elif flood_stage_cfs and streamflow_cfs >= flood_stage_cfs * 0.8:
        risk_level = "Moderate"
        ratio = streamflow_cfs / flood_stage_cfs
        risk_score = 4.0 + (ratio - 0.8) * 15.0
    elif streamflow_cfs > 35315:   # ~1000 m³/s
        risk_level = "Moderate"
        risk_score = min(7.0, 3.0 + (streamflow_cfs / 70630.0) * 2.0)
    elif streamflow_cfs > 17658:   # ~500 m³/s
        risk_level = "Low"
        risk_score = 2.0 + (streamflow_cfs / 17658.0)
    else:
        risk_level = "Low"
        risk_score = min(3.0, max(0.5, streamflow_cfs / 7063.0))
    return risk_level, round(risk_score, 1)


def calculate_trend(current_flow: float, previous_flow: float, time_diff_hours: float) -> Tuple[str, float]:
    """Calculate flow trend."""
    if time_diff_hours <= 0:
        return "stable", 0.0
    rate_per_hour = (current_flow - previous_flow) / time_diff_hours
    if abs(rate_per_hour) < 1.0:
        trend = "stable"
    elif rate_per_hour > 0:
        trend = "rising"
    else:
        trend = "falling"
    return trend, round(rate_per_hour, 1)


def update_watershed_with_discharge_data(db_path: str, data: StreamflowData) -> bool:
    """Update watershed in DB with Open-Meteo discharge data."""
    try:
        watersheds = db.get_watersheds(db_path)
        target = None
        for w in watersheds:
            if data.site_code in w.get('name', '') or data.site_name.lower() in w.get('name', '').lower():
                target = w
                break
        if not target:
            log.warning(f"No matching watershed for site {data.site_code} ({data.site_name})")
            return False

        current_flow = target['current_streamflow_cfs']
        flood_stage = target.get('flood_stage_cfs')
        risk_level, risk_score = calculate_risk_level(data.streamflow_cfs, flood_stage)
        trend, trend_rate = calculate_trend(data.streamflow_cfs, current_flow, 1.0)

        rows = db.update_watershed_with_api_data(
            db_path, target['id'],
            data.streamflow_cfs, risk_level, risk_score,
            data_source='openmeteo',
            data_quality='provisional',
            trend=trend, trend_rate=trend_rate
        )
        try:
            db.insert_risk_trend(db_path, target['id'], risk_score, data.streamflow_cfs)
        except Exception as e:
            log.warning(f"Could not insert risk trend: {e}")

        log.info(f"Updated watershed {target['name']}: {data.streamflow_cfs:.0f} CFS, {risk_level} risk")
        return rows > 0
    except Exception as e:
        log.error(f"Error updating watershed with discharge data: {e}")
        return False


def fetch_and_update_usgs_data(db_path: str, site_codes: Optional[List[str]] = None,
                                region_code: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetch river discharge from Open-Meteo and update watershed DB.
    Function name kept for backward compatibility.
    """
    if not settings.enable_real_time_data:
        return {"success": False, "message": "Real-time data integration disabled"}

    if site_codes is None:
        if region_code:
            site_codes = get_major_river_sites_by_region(region_code)
        else:
            site_codes = get_major_india_river_sites()

    api = OpenMeteoFloodAPI(timeout=settings.usgs_api_timeout)
    results = {
        "success": True,
        "updated_count": 0,
        "failed_count": 0,
        "errors": [],
        "region_code": region_code or "IN-GANGA",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        streamflow_data = api.get_streamflow_data(site_codes)
        if not streamflow_data:
            results["success"] = False
            results["message"] = "No discharge data retrieved from Open-Meteo"
            return results

        for data in streamflow_data:
            try:
                if update_watershed_with_discharge_data(db_path, data):
                    results["updated_count"] += 1
                else:
                    results["failed_count"] += 1
            except Exception as e:
                results["failed_count"] += 1
                results["errors"].append(f"Failed to update {data.site_code}: {e}")

        results["message"] = f"Updated {results['updated_count']} watersheds, {results['failed_count']} failed"
        log.info(f"India discharge update completed: {results['message']}")
        return results

    except Exception as e:
        results["success"] = False
        results["message"] = f"Discharge fetch failed: {e}"
        results["errors"].append(str(e))
        log.error(f"Discharge fetch failed: {e}")
        return results


def fetch_and_store_imd_alerts(db_path: str) -> Dict[str, Any]:
    """
    Fetch India flood alerts via Open-Meteo weather warnings.
    Function name kept for backward compatibility.
    Uses Open-Meteo heavy precipitation forecasts as proxy alerts.
    """
    results = {
        "success": True,
        "alerts_fetched": 0,
        "alerts_stored": 0,
        "alerts_skipped": 0,
        "errors": [],
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    if not settings.enable_real_time_data:
        return {"success": False, "message": "Real-time data integration disabled"}

    try:
        imd_api = IMDWeatherAPI()
        watersheds = db.get_watersheds(db_path)
        if not watersheds:
            return {"success": False, "message": "No watersheds in database"}

        # Check each watershed's location for heavy rainfall warnings
        for watershed in watersheds[:8]:   # Limit to first 8 to avoid API hammering
            lat = watershed.get('location_lat')
            lng = watershed.get('location_lng')
            if not lat or not lng:
                continue

            weather = imd_api.get_weather(lat, lng)
            if not weather:
                continue

            # Check for heavy rainfall (>50mm/day = IMD heavy rain threshold)
            daily = weather.get('daily', {})
            precip_list = daily.get('precipitation_sum', [])

            results["alerts_fetched"] += 1
            max_precip = max(precip_list) if precip_list else 0

            if max_precip >= 115.6:      # IMD: Extremely Heavy Rain
                severity_label = "High"
                alert_type = "Extremely Heavy Rainfall Warning"
            elif max_precip >= 64.5:     # IMD: Very Heavy Rain
                severity_label = "High"
                alert_type = "Very Heavy Rainfall Warning"
            elif max_precip >= 15.6:     # IMD: Heavy Rain
                severity_label = "Moderate"
                alert_type = "Heavy Rainfall Warning"
            else:
                continue   # Normal rainfall, no alert needed

            message = (f"{alert_type}: Expected {max_precip:.0f}mm rainfall near "
                       f"{watershed['name']}. Flood risk elevated.")

            expires_time = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()

            alert_id = db.insert_imd_alert(
                db_path,
                alert_type=alert_type,
                watershed_id=watershed['id'],
                message=message,
                severity=severity_label,
                issued_time=datetime.now(timezone.utc).isoformat(),
                expires_time=expires_time,
                counties=watershed.get('region', ''),
                imd_id=f"imd_{watershed['id']}_{datetime.now().strftime('%Y%m%d%H')}"
            )
            if alert_id:
                results["alerts_stored"] += 1
            else:
                results["alerts_skipped"] += 1

        results["message"] = (f"Checked {results['alerts_fetched']} locations, "
                               f"stored {results['alerts_stored']} alerts, "
                               f"skipped {results['alerts_skipped']} duplicates")
        log.info(f"India rainfall alert update: {results['message']}")
        return results

    except Exception as e:
        results["success"] = False
        results["message"] = f"Alert fetch failed: {e}"
        results["errors"].append(str(e))
        log.error(f"India alert fetch failed: {e}")
        return results


def match_alert_to_watersheds(area_description: str, watersheds: List[Dict]) -> List[Dict]:
    """Match an alert area description to watersheds."""
    if not area_description or not watersheds:
        return []
    matched = []
    area_parts = [p.strip().lower() for p in area_description.replace(';', ',').split(',')]
    for w in watersheds:
        name = w.get('name', '').lower()
        for area in area_parts:
            if area in name or name in area:
                matched.append(w)
                break
    return matched


def create_watersheds_from_usgs_sites(
    db_path: str,
    limit: int = 12,
    region_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create watershed rows in the DB from India river monitoring sites.
    Function name kept for backward compatibility with server.py.
    Uses Open-Meteo Flood API instead of USGS.
    """
    from . import db as _db

    effective_region = region_code or "IN-GANGA"
    site_codes = get_major_river_sites_by_region(effective_region)
    if not site_codes:
        site_codes = get_major_india_river_sites()
    site_codes = site_codes[:limit]

    # CWC approximate flood-stage thresholds (m³/s converted to CFS: ×35.3147)
    FLOOD_STAGE_CFS: Dict[str, float] = {
        "ganga_patna":               1_200_000,
        "ganga_haridwar":              200_000,
        "ganga_allahabad":             800_000,
        "ganga_varanasi":            1_000_000,
        "brahmaputra_guwahati":      2_000_000,
        "brahmaputra_dibrugarh":     1_500_000,
        "yamuna_delhi":                300_000,
        "mahanadi_hirakud":            600_000,
        "mahanadi_cuttack":            700_000,
        "godavari_rajahmundry":      1_500_000,
        "godavari_nashik":             100_000,
        "krishna_vijayawada":          800_000,
        "narmada_sardar_sarovar":      700_000,
        "kaveri_krishnarajasagara":    150_000,
    }

    created = 0
    skipped = 0
    errors: List[str] = []

    region_cfg = get_region_config(effective_region) or {}
    region_name = region_cfg.get("name", effective_region)

    for code in site_codes:
        site = INDIA_RIVER_SITES.get(code)
        if not site:
            skipped += 1
            continue

        # RiverSite is a dataclass: (site_code, site_name, latitude, longitude)
        site_name = site.site_name
        lat = site.latitude
        lon = site.longitude

        flood_stage = FLOOD_STAGE_CFS.get(code, 500_000)

        try:
            _db.insert_watershed(
                db_path,
                name=site_name,
                region=region_name,
                region_code=effective_region,
                lat=lat,
                lng=lon,
                flood_stage=flood_stage,
                risk_level="Low",
                risk_score=1.0,
                river_site_code=code,
                data_source="openmeteo",
            )
            created += 1
        except Exception as e:
            errors.append(f"{code}: {e}")
            skipped += 1

    log.info(f"Created {created} India watershed records for region {effective_region}")
    return {
        "created_count": created,
        "skipped_count": skipped,
        "errors": errors,
        "region_code": effective_region,
    }
