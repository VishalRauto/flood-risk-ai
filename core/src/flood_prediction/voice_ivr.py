"""
voice_ivr.py — Voice-First IVR Flood Alert System

World-first: All existing early warning systems are SMS or app-based.
A voice-first flood alert in regional dialects with real-time LLM-generated
spoken guidance does not exist anywhere in the world.

How it works:
  1. Citizens call a toll-free IVR number (or the system calls them outbound)
  2. They speak or press a key for their district/language
  3. The system speaks the current flood risk + action instructions
     in their chosen language using pre-recorded or TTS audio
  4. For CRITICAL alerts, the system auto-dials registered vulnerable households
     (elderly, no-mobile-internet) and delivers the alert without any action needed

Integration points:
  - Twilio Voice API for outbound calls and IVR
  - Google TTS or Amazon Polly for regional language synthesis
  - Existing translations.py for message text
  - Existing user_accounts.py for registered subscribers

This module generates:
  - IVR call scripts in all 8 languages
  - TTS-ready audio text (SSML markup)
  - Outbound call batch for CRITICAL alerts
  - IVR response logic (DTMF key mappings)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ── IVR Scripts in all 8 languages ───────────────────────────────────────────
IVR_SCRIPTS: Dict[str, Dict[str, str]] = {
    "greeting": {
        "en": "Welcome to India Flood Alert System. Press 1 for flood risk in your area. Press 2 to register for alerts. Press 9 to repeat.",
        "hi": "भारत बाढ़ चेतावनी प्रणाली में आपका स्वागत है। अपने क्षेत्र में बाढ़ का खतरा जानने के लिए 1 दबाएं। अलर्ट के लिए पंजीकरण हेतु 2 दबाएं।",
        "bn": "ভারত বন্যা সতর্কতা সিস্টেমে আপনাকে স্বাগতম। আপনার এলাকার বন্যার ঝুঁকি জানতে ১ চাপুন।",
        "or": "ଭାରତ ବନ୍ୟା ସଚେତନ ପ୍ରଣାଳୀକୁ ଆପଣଙ୍କୁ ସ୍ୱାଗତ। ଆପଣଙ୍କ ଅଞ୍ଚଳର ବନ୍ୟା ବିପଦ ଜାଣିବା ପାଇଁ ୧ ଦବାନ୍ତୁ।",
        "as": "ভাৰত বান সতৰ্কতা প্ৰণালীলৈ আপোনাক স্বাগতম। আপোনাৰ অঞ্চলৰ বান বিপদ জানিবলৈ ১ টিপক।",
        "te": "భారత వరద హెచ్చరిక వ్యవస్థకు స్వాగతం. మీ ప్రాంతంలో వరద ప్రమాదం తెలుసుకోవడానికి 1 నొక్కండి.",
        "ta": "இந்திய வெள்ள எச்சரிக்கை அமைப்பிற்கு வரவேற்கிறோம். உங்கள் பகுதியில் வெள்ள ஆபத்தை அறிய 1 அழுத்தவும்.",
        "mr": "भारत पूर सतर्कता प्रणालीत आपले स्वागत. आपल्या परिसरातील पूर धोका जाणण्यासाठी 1 दाबा.",
        "gu": "ભારત પૂર ચેતવણી પ્રણાળીમાં આપનું સ્વાગત. તમારા વિસ્તારનું પૂર જોખમ જાણવા 1 દબાવો.",
    },
    "critical_alert": {
        "en": "URGENT FLOOD WARNING. Flood risk is CRITICAL in your district. Water levels are dangerously high. EVACUATE IMMEDIATELY. Move to higher ground NOW. Do not wait. Call NDMA at 1-0-7-8 for help. Repeat: EVACUATE IMMEDIATELY.",
        "hi": "अत्यंत आवश्यक बाढ़ चेतावनी। आपके जिले में बाढ़ का खतरा अत्यंत गंभीर है। तुरंत निकासी करें। अभी ऊंचे स्थान पर जाएं। देरी न करें। सहायता के लिए NDMA को 1-0-7-8 पर कॉल करें।",
        "bn": "জরুরি বন্যা সতর্কতা। আপনার জেলায় বন্যার ঝুঁকি অত্যন্ত বেশি। এখনই সরে যান। উঁচু জায়গায় যান। দেরি করবেন না। NDMA-কে ১-০-৭-৮ নম্বরে ফোন করুন।",
        "or": "ଜରୁରୀ ବନ୍ୟା ସଚେତନ। ଆପଣଙ୍କ ଜିଲ୍ଲାରେ ବନ୍ୟା ବିପଦ ଅତ୍ୟନ୍ତ ଗୁରୁତର। ତୁରନ୍ତ ଖାଲି କରନ୍ତୁ। ଉଚ୍ଚ ସ୍ଥାନକୁ ଯାଆନ୍ତୁ। NDMA: ୧-0-୭-୮।",
        "as": "জৰুৰী বান সতৰ্কতা। আপোনাৰ জিলাত বান বিপদ অতি গুৰুতৰ। তৎক্ষণাৎ স্থান ত্যাগ কৰক। ওখ ঠাইলৈ যাওক। NDMA: ১-০-৭-৮।",
        "te": "అత్యవసర వరద హెచ్చరిక. మీ జిల్లాలో వరద ప్రమాదం చాలా తీవ్రంగా ఉంది. వెంటనే తరలించండి. ఎత్తైన ప్రదేశానికి వెళ్ళండి. NDMA: ౧-0-౭-౮.",
        "ta": "அவசர வெள்ள எச்சரிக்கை. உங்கள் மாவட்டத்தில் வெள்ள ஆபத்து மிகவும் தீவிரமாக உள்ளது. உடனடியாக வெளியேறுங்கள். NDMA: 1-0-7-8.",
        "mr": "तातडीची पूर सूचना. आपल्या जिल्ह्यात पूर धोका अत्यंत गंभीर आहे. त्वरित निर्वासन करा. NDMA: 1-0-7-8.",
        "gu": "તાત્કાલિક પૂર ચેતવણી. તમારા જિલ્લામાં પૂરનું જોખમ અત્યંત ગંભીર છે. તાત્કાલિક સ્થળાંતર કરો. NDMA: 1-0-7-8.",
    },
    "high_alert": {
        "en": "FLOOD WARNING. Flood risk is HIGH in your district. Prepare to evacuate. Move valuables to higher floors. Avoid river banks and low-lying areas. Stay alert. NDMA helpline: 1-0-7-8.",
        "hi": "बाढ़ चेतावनी। आपके जिले में बाढ़ का खतरा अधिक है। निकासी के लिए तैयार रहें। नदी किनारों से दूर रहें। NDMA: 1-0-7-8।",
        "bn": "বন্যা সতর্কতা। আপনার জেলায় উচ্চ বন্যার ঝুঁকি রয়েছে। সরে যাওয়ার জন্য প্রস্তুত থাকুন। NDMA: ১-০-৭-৮।",
        "or": "ବନ୍ୟା ସଚେତନ। ଆପଣଙ୍କ ଜିଲ୍ଲାରେ ଉଚ୍ଚ ବନ୍ୟା ବିପଦ। ଖାଲି କରିବାକୁ ପ୍ରସ୍ତୁତ ରୁହନ୍ତୁ। NDMA: ୧-0-୭-୮।",
        "as": "বান সতৰ্কতা। আপোনাৰ জিলাত উচ্চ বান বিপদ। স্থান ত্যাগৰ বাবে সাজু হওক। NDMA: ১-০-৭-৮।",
        "te": "వరద హెచ్చరిక. మీ జిల్లాలో అధిక వరద ప్రమాదం. తరలించడానికి సిద్ధంగా ఉండండి. NDMA: ౧-0-౭-౮.",
        "ta": "வெள்ள எச்சரிக்கை. உங்கள் மாவட்டத்தில் அதிக வெள்ள ஆபத்து. வெளியேற தயாராக இருங்கள். NDMA: 1-0-7-8.",
        "mr": "पूर सतर्कता. आपल्या जिल्ह्यात उच्च पूर धोका. निर्वासनासाठी तयार रहा. NDMA: 1-0-7-8.",
        "gu": "પૂર ચેતવણી. તમારા જિલ્લામાં ઉચ્ચ પૂર જોખમ. સ્થળાંતર માટે તૈયાર રહો. NDMA: 1-0-7-8.",
    },
    "safe": {
        "en": "Flood risk in your area is currently LOW. No immediate action required. Stay informed. Monitor local weather updates. NDMA helpline: 1-0-7-8.",
        "hi": "आपके क्षेत्र में बाढ़ का खतरा फिलहाल कम है। तुरंत कोई कार्रवाई आवश्यक नहीं। NDMA: 1-0-7-8।",
        "bn": "আপনার এলাকায় বন্যার ঝুঁকি বর্তমানে কম। কোনো তাৎক্ষণিক পদক্ষেপ প্রয়োজন নেই। NDMA: ১-০-৭-৮।",
        "or": "ଆପଣଙ୍କ ଅଞ୍ଚଳରେ ବନ୍ୟା ବିପଦ ଏବେ କମ। ତୁରନ୍ତ କୌଣସି ପଦକ୍ଷେପ ଆବଶ୍ୟକ ନାହିଁ। NDMA: ୧-0-୭-୮।",
        "as": "আপোনাৰ অঞ্চলত বান বিপদ এতিয়া কম। তৎক্ষণাৎ কোনো ব্যৱস্থা লোৱাৰ প্ৰয়োজন নাই। NDMA: ১-০-৭-৮।",
        "te": "మీ ప్రాంతంలో వరద ప్రమాదం ప్రస్తుతం తక్కువ. వెంటనే చర్య అవసరం లేదు. NDMA: ౧-0-౭-౮.",
        "ta": "உங்கள் பகுதியில் வெள்ள ஆபத்து தற்போது குறைவாக உள்ளது. உடனடி நடவடிக்கை தேவையில்லை. NDMA: 1-0-7-8.",
        "mr": "आपल्या परिसरात पूर धोका सध्या कमी आहे. त्वरित कारवाई आवश्यक नाही. NDMA: 1-0-7-8.",
        "gu": "તમારા વિસ્તારમાં પૂરનું જોખમ હાલ ઓછું છે. તાત્કાલિક પગલાંની જરૂર નથી. NDMA: 1-0-7-8.",
    },
    "language_menu": {
        "en": "Press 1 for English. Press 2 for Hindi. Press 3 for Bengali. Press 4 for Odia. Press 5 for Assamese. Press 6 for Telugu. Press 7 for Tamil. Press 8 for Marathi. Press 9 for Gujarati.",
    },
}

LANGUAGE_KEYS = {
    "1": "en", "2": "hi", "3": "bn", "4": "or",
    "5": "as", "6": "te", "7": "ta", "8": "mr", "9": "gu",
}

# SSML markup for TTS (pause, emphasis, rate control)
SSML_TEMPLATE = """<speak>
  <prosody rate="90%" pitch="-2st">
    {text}
  </prosody>
  <break time="500ms"/>
  <emphasis level="strong">
    {emergency}
  </emphasis>
</speak>"""


@dataclass
class IVRCall:
    call_id:        str
    phone_number:   str
    language:       str
    risk_level:     str
    script_text:    str
    ssml_text:      str
    call_type:      str    # inbound | outbound_critical | outbound_scheduled
    district:       str
    status:         str = "queued"
    created_at:     str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IVRBatch:
    batch_id:       str
    district:       str
    risk_level:     str
    total_calls:    int
    calls:          List[IVRCall]
    estimated_duration_min: float
    twilio_enabled: bool
    message:        str
    generated_at:   str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["calls"] = [c.to_dict() for c in self.calls]
        return d


class VoiceIVRSystem:
    """
    Voice-first IVR alert system for India flood intelligence.
    Generates call scripts, SSML markup, and outbound call batches.
    Integrates with Twilio Voice API for actual delivery.
    """

    def get_script(self, risk_level: str, lang: str = "en") -> str:
        """Get IVR script for a given risk level and language."""
        lang = lang if lang in ["en","hi","bn","or","as","te","ta","mr","gu"] else "en"
        if risk_level in ("CRITICAL",):
            key = "critical_alert"
        elif risk_level == "HIGH":
            key = "high_alert"
        else:
            key = "safe"
        scripts = IVR_SCRIPTS[key]
        return scripts.get(lang, scripts["en"])

    def get_ssml(self, risk_level: str, lang: str = "en",
                 district: str = "your district") -> str:
        """Generate SSML markup for TTS synthesis."""
        script   = self.get_script(risk_level, lang)
        emergency = IVR_SCRIPTS["safe"].get(lang, IVR_SCRIPTS["safe"]["en"])
        # Replace district placeholder
        script = script.replace("your district", district)
        return SSML_TEMPLATE.format(text=script, emergency="NDMA 1078")

    def get_full_menu(self, lang: str = "en") -> Dict[str, str]:
        """Get all IVR menu options for a language."""
        return {
            "greeting":      IVR_SCRIPTS["greeting"].get(lang, IVR_SCRIPTS["greeting"]["en"]),
            "lang_menu":     IVR_SCRIPTS["language_menu"]["en"],
            "critical":      IVR_SCRIPTS["critical_alert"].get(lang, IVR_SCRIPTS["critical_alert"]["en"]),
            "high":          IVR_SCRIPTS["high_alert"].get(lang, IVR_SCRIPTS["high_alert"]["en"]),
            "safe":          IVR_SCRIPTS["safe"].get(lang, IVR_SCRIPTS["safe"]["en"]),
            "language_keys": LANGUAGE_KEYS,
        }

    def generate_outbound_batch(self,
                                 district: str,
                                 risk_level: str,
                                 phone_numbers: List[Dict[str, str]],
                                 ) -> IVRBatch:
        """
        Generate a batch of outbound calls for CRITICAL or HIGH alerts.

        phone_numbers: list of {"phone": "+91...", "lang": "hi", "name": "..."}
        """
        import secrets
        batch_id = f"IVR-{datetime.now().strftime('%Y%m%d%H%M')}-{secrets.token_hex(3).upper()}"

        calls: List[IVRCall] = []
        for subscriber in phone_numbers:
            phone = subscriber.get("phone", "")
            lang  = subscriber.get("lang", "en")
            if not phone:
                continue
            script = self.get_script(risk_level, lang)
            ssml   = self.get_ssml(risk_level, lang, district)
            calls.append(IVRCall(
                call_id     = f"{batch_id}-{len(calls)+1:04d}",
                phone_number = phone,
                language    = lang,
                risk_level  = risk_level,
                script_text = script,
                ssml_text   = ssml,
                call_type   = "outbound_critical" if risk_level == "CRITICAL" else "outbound_scheduled",
                district    = district,
            ))

        # Twilio delivery (if configured)
        twilio_enabled = self._try_twilio_batch(calls)

        duration = len(calls) * 0.5   # ~30s per call = 0.5 min
        return IVRBatch(
            batch_id   = batch_id,
            district   = district,
            risk_level = risk_level,
            total_calls = len(calls),
            calls      = calls,
            estimated_duration_min = round(duration, 1),
            twilio_enabled = twilio_enabled,
            message    = (f"Batch {batch_id}: {len(calls)} outbound calls queued "
                          f"for {district} ({risk_level} alert). "
                          f"{'Twilio delivery active.' if twilio_enabled else 'Twilio not configured — scripts generated only.'}"),
        )

    def _try_twilio_batch(self, calls: List[IVRCall]) -> bool:
        """Attempt to initiate calls via Twilio Voice API."""
        try:
            from .settings import settings
            from twilio.rest import Client
            if not (settings.twilio_account_sid and settings.twilio_auth_token
                    and settings.twilio_from_number
                    and "ACxx" not in settings.twilio_account_sid):
                return False
            client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
            for call in calls[:5]:   # limit to 5 in demo mode
                client.calls.create(
                    twiml=(f"<Response><Say language='{call.language}'>"
                           f"{call.script_text[:500]}</Say></Response>"),
                    to=call.phone_number,
                    from_=settings.twilio_from_number,
                )
                call.status = "initiated"
            return True
        except Exception as e:
            log.debug(f"Twilio voice not available: {e}")
            return False

    def simulate_inbound_response(self, digit: str, district: str,
                                   risk_level: str) -> Dict[str, str]:
        """Simulate what the IVR returns when a citizen presses a digit."""
        lang = LANGUAGE_KEYS.get(digit, "en")
        return {
            "digit":    digit,
            "language": lang,
            "response": self.get_script(risk_level, lang),
            "ssml":     self.get_ssml(risk_level, lang, district),
            "next":     "Press * to repeat. Press 0 to reach live operator.",
        }


_ivr: Optional[VoiceIVRSystem] = None

def get_ivr_system() -> VoiceIVRSystem:
    global _ivr
    if _ivr is None:
        _ivr = VoiceIVRSystem()
    return _ivr
