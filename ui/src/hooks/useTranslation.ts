/**
 * useTranslation.ts
 * 
 * Multilingual hook for India Flood Intelligence.
 * Supports: English, Hindi, Bengali, Odia, Assamese,
 *           Telugu, Tamil, Marathi, Gujarati
 *
 * Usage:
 *   const { t, lang, setLang, languages } = useTranslation()
 *   <h1>{t('flood_risk_title')}</h1>
 */

import { useState, useCallback } from 'react'

export interface Language {
  code: string
  name: string
  native: string
}

// ── Inline translations (no network call needed) ──────────────────────────────
const TRANSLATIONS: Record<string, Record<string, string>> = {
  risk_critical: {
    en: 'CRITICAL', hi: 'अत्यंत खतरनाक', bn: 'অতিমাত্রায় বিপজ্জনক',
    or: 'ଅତ୍ୟନ୍ତ ବିପଜ୍ଜନକ', as: 'অতি বিপজ্জনক', te: 'అత్యంత ప్రమాదకర',
    ta: 'மிக அபாயகரமான', mr: 'अत्यंत धोकादायक', gu: 'અત્યંત જોખમી',
  },
  risk_high: {
    en: 'HIGH', hi: 'उच्च खतरा', bn: 'উচ্চ ঝুঁকি',
    or: 'ଉଚ୍ଚ ବିପଦ', as: 'উচ্চ বিপদ', te: 'అధిక ప్రమాదం',
    ta: 'அதிக ஆபத்து', mr: 'उच्च धोका', gu: 'ઉચ્ચ જોખમ',
  },
  risk_moderate: {
    en: 'MODERATE', hi: 'मध्यम खतरा', bn: 'মাঝারি ঝুঁকি',
    or: 'ମଧ୍ୟମ ବିପଦ', as: 'মধ্যমীয়া বিপদ', te: 'మధ్యస్థ ప్రమాదం',
    ta: 'மிதமான ஆபத்து', mr: 'मध्यम धोका', gu: 'મધ્યમ જોખમ',
  },
  risk_low: {
    en: 'LOW', hi: 'कम खतरा', bn: 'কম ঝুঁকি',
    or: 'କମ ବିପଦ', as: 'কম বিপদ', te: 'తక్కువ ప్రమాదం',
    ta: 'குறைந்த ஆபத்து', mr: 'कमी धोका', gu: 'ઓછું જોખમ',
  },
  action_critical: {
    en: 'Evacuate immediately. Move to higher ground now. Call NDMA: 1078',
    hi: 'तुरंत निकासी करें। अभी ऊँचे स्थान पर जाएं। NDMA: 1078',
    bn: 'এখনই সরে যান। উঁচু জায়গায় যান। NDMA: 1078',
    or: 'ତୁରନ୍ତ ଖାଲି କରନ୍ତୁ। ଉଚ୍ଚ ସ୍ଥାନକୁ ଯାଆନ୍ତୁ। NDMA: 1078',
    as: 'তৎক্ষণাৎ স্থান ত্যাগ কৰক। ওখ ঠাইলৈ যাওক। NDMA: 1078',
    te: 'వెంటనే తరలించండి. ఎత్తైన ప్రదేశానికి వెళ్ళండి. NDMA: 1078',
    ta: 'உடனடியாக வெளியேறுங்கள். உயர் நிலத்திற்கு செல்லுங்கள். NDMA: 1078',
    mr: 'त्वरित निर्वासन करा. उंच ठिकाणी जा. NDMA: 1078',
    gu: 'તાત્કાલિક સ્થળાંતર કરો. ઊંચી જગ્યાએ જાઓ. NDMA: 1078',
  },
  action_high: {
    en: 'Prepare to evacuate. Avoid river banks. Stay alert. NDMA: 1078',
    hi: 'निकासी के लिए तैयार रहें। नदी किनारे से दूर रहें। NDMA: 1078',
    bn: 'সরে যাওয়ার জন্য প্রস্তুত থাকুন। NDMA: 1078',
    or: 'ଖାଲି କରିବାକୁ ପ୍ରସ୍ତୁତ ରୁହନ୍ତୁ। NDMA: 1078',
    as: 'স্থান ত্যাগৰ বাবে সাজু হওক। NDMA: 1078',
    te: 'తరలించడానికి సిద్ధంగా ఉండండి. NDMA: 1078',
    ta: 'வெளியேற தயாராக இருங்கள். NDMA: 1078',
    mr: 'निर्वासनासाठी तयार रहा. NDMA: 1078',
    gu: 'સ્થળાંતર માટે તૈયાર રહો. NDMA: 1078',
  },
  action_moderate: {
    en: 'Stay alert. Monitor river levels. Follow local authority instructions.',
    hi: 'सतर्क रहें। नदी का जल स्तर देखते रहें। स्थानीय प्रशासन का पालन करें।',
    bn: 'সতর্ক থাকুন। নদীর স্তর পর্যবেক্ষণ করুন।',
    or: 'ସତର୍କ ରୁହନ୍ତୁ। ନଦୀ ସ୍ତର ଦେଖନ୍ତୁ।',
    as: 'সতৰ্ক থাকক। নদীৰ স্তৰ পৰ্যবেক্ষণ কৰক।',
    te: 'అప్రమత్తంగా ఉండండి. నది స్థాయిలను పర్యవేక్షించండి.',
    ta: 'விழிப்புடன் இருங்கள். ஆற்று நீர் மட்டத்தை கவனியுங்கள்.',
    mr: 'सतर्क राहा. नदीची पातळी पहा.',
    gu: 'સાવધ રહો. નદીના સ્તરનું નિરીક્ષણ કરો.',
  },
  action_low: {
    en: 'No immediate action needed. Stay informed via weather updates.',
    hi: 'अभी कोई कार्रवाई आवश्यक नहीं। मौसम अपडेट से जानकारी रखें।',
    bn: 'এখনই কোনো পদক্ষেপের দরকার নেই।',
    or: 'ତୁରନ୍ତ କୌଣସି ପଦକ୍ଷେପ ଆବଶ୍ୟକ ନାହିଁ।',
    as: 'এতিয়াই কোনো ব্যৱস্থা লোৱাৰ প্ৰয়োজন নাই।',
    te: 'ఇప్పుడే చర్య అవసరం లేదు.',
    ta: 'இப்போது எந்த நடவடிக்கையும் தேவையில்லை.',
    mr: 'आत्ता कोणतीही कारवाई आवश्यक नाही.',
    gu: 'હમણાં કોઈ કાર્યવાહી જરૂરી નથી.',
  },
  search_placeholder: {
    en: 'Search city or district...', hi: 'शहर या जिला खोजें...',
    bn: 'শহর বা জেলা অনুসন্ধান করুন...', or: 'ସହର ବା ଜିଲ୍ଲା ଖୋଜନ୍ତୁ...',
    as: 'চহর বা জিলা বিচাৰক...', te: 'నగరం లేదా జిల్లాను వెతకండి...',
    ta: 'நகரம் அல்லது மாவட்டத்தை தேடுங்கள்...', mr: 'शहर किंवा जिल्हा शोधा...',
    gu: 'શહેર અથવા જિલ્લો શોધો...',
  },
  flood_risk_title: {
    en: 'Flood Risk in Your Area', hi: 'आपके क्षेत्र में बाढ़ का खतरा',
    bn: 'আপনার এলাকায় বন্যার ঝুঁকি', or: 'ଆପଣଙ୍କ ଅଞ୍ଚଳରେ ବନ୍ୟା ବିପଦ',
    as: 'আপোনাৰ অঞ্চলত বান বিপদ', te: 'మీ ప్రాంతంలో వరద ప్రమాదం',
    ta: 'உங்கள் பகுதியில் வெள்ள ஆபத்து', mr: 'तुमच्या परिसरात पूर धोका',
    gu: 'તમારા વિસ્તારમાં પૂરનું જોખમ',
  },
  what_to_do: {
    en: 'What should I do?', hi: 'मुझे क्या करना चाहिए?',
    bn: 'আমার কী করা উচিত?', or: 'ମୁଁ କ\'ଣ କରିବା ଉଚିତ?',
    as: 'মই কি কৰা উচিত?', te: 'నేను ఏమి చేయాలి?',
    ta: 'நான் என்ன செய்ய வேண்டும்?', mr: 'मी काय करावे?',
    gu: 'મારે શું કરવું જોઈએ?',
  },
  emergency_contact: {
    en: 'Emergency: NDMA 1078', hi: 'आपातकाल: NDMA 1078',
    bn: 'জরুরি: NDMA 1078', or: 'ଜରୁରୀ: NDMA 1078',
    as: 'জৰুৰী: NDMA 1078', te: 'అత్యవసర: NDMA 1078',
    ta: 'அவசர: NDMA 1078', mr: 'आणीबाणी: NDMA 1078',
    gu: 'કટોકટી: NDMA 1078',
  },
  last_updated: {
    en: 'Last updated', hi: 'अंतिम अपडेट', bn: 'সর্বশেষ আপডেট',
    or: 'ଶେଷ ଅଦ୍ୟତନ', as: 'শেষ আপডেট', te: 'చివరిగా నవీకరించబడింది',
    ta: 'கடைசியாக புதுப்பிக்கப்பட்டது', mr: 'शेवटचे अद्यतन', gu: 'છેલ્લે અપડેટ',
  },
  trend_rising:  { en: 'Rising ↑',  hi: 'बढ़ रहा है ↑', bn: 'বাড়ছে ↑',  or: 'ବଢ଼ୁଛି ↑',   as: 'বাঢ়িছে ↑',  te: 'పెరుగుతోంది ↑', ta: 'உயர்கிறது ↑',  mr: 'वाढत आहे ↑',       gu: 'વધી રહ્યું ↑'  },
  trend_falling: { en: 'Falling ↓', hi: 'घट रहा है ↓',  bn: 'কমছে ↓',   or: 'କମୁଛି ↓',    as: 'কমিছে ↓',   te: 'తగ్గుతోంది ↓',  ta: 'குறைகிறது ↓', mr: 'कमी होत आहे ↓',    gu: 'ઘટી રહ્યું ↓' },
  trend_stable:  { en: 'Stable →',  hi: 'स्थिर →',       bn: 'স্থিতিশীল →', or: 'ସ୍ଥିର →', as: 'স্থিৰ →',   te: 'స్థిరంగా →',    ta: 'நிலையான →',   mr: 'स्थिर →',           gu: 'સ્થિર →'      },
  register:      { en: 'Register for Alerts', hi: 'अलर्ट के लिए पंजीकरण करें', bn: 'সতর্কতার জন্য নিবন্ধন করুন', or: 'ସତର୍କତା ପାଇଁ ପଞ୍ଜୀକରଣ', as: 'সতৰ্কতাৰ বাবে পঞ্জীয়ন', te: 'హెచ్చరికల కోసం నమోదు', ta: 'பதிவு செய்யுங்கள்', mr: 'नोंदणी करा', gu: 'નોંધણી કરો' },
  login:         { en: 'Login', hi: 'लॉग इन', bn: 'লগইন', or: 'ଲଗ ଇନ', as: 'লগ ইন', te: 'లాగిన్', ta: 'உள்நுழை', mr: 'लॉगिन', gu: 'લૉગ ઇન' },
  checking_risk: { en: 'Checking flood risk...', hi: 'बाढ़ खतरा जांच रहे हैं...', bn: 'বন্যার ঝুঁকি পরীক্ষা করা হচ্ছে...', or: 'ବନ୍ୟା ବିପଦ ଯାଞ୍ଚ ହେଉଛି...', as: 'বান বিপদ পৰীক্ষা কৰা হৈছে...', te: 'వరద ప్రమాదం తనిఖీ చేస్తోంది...', ta: 'வெள்ள ஆபத்து சரிபார்க்கப்படுகிறது...', mr: 'पूर धोका तपासत आहे...', gu: 'પૂરનું જોખમ ચકાસવામાં આવી રહ્યું છે...' },
  sites_checked: { en: 'sites checked', hi: 'स्थान जांचे गए', bn: 'সাইট পরীক্ষা করা হয়েছে', or: 'ସ୍ଥାନ ଯାଞ୍ଚ', as: 'স্থান পৰীক্ষা', te: 'సైట్లు తనిఖీ', ta: 'தளங்கள் சரிபார்க்கப்பட்டன', mr: 'ठिकाणे तपासली', gu: 'સ્થળો ચકાસ્યા' },
  rising_sites:  { en: 'rising', hi: 'बढ़ रहे हैं', bn: 'বাড়ছে', or: 'ବଢ଼ୁଛି', as: 'বাঢ়িছে', te: 'పెరుగుతున్నాయి', ta: 'உயர்கின்றன', mr: 'वाढत आहे', gu: 'વધી રહ્યા છે' },
  view_dashboard:{ en: 'View Full Dashboard →', hi: 'पूरा डैशबोर्ड देखें →', bn: 'পূর্ণ ড্যাশবোর্ড দেখুন →', or: 'ସମ୍ପୂର୍ଣ ଡ୍ୟାଶବୋର୍ଡ ଦେଖନ୍ତୁ →', as: 'সম্পূৰ্ণ ডেচবৰ্ড চাওক →', te: 'పూర్తి డాష్‌బోర్డ్ చూడండి →', ta: 'முழு டாஷ்போர்டைப் பார்க்கவும் →', mr: 'पूर्ण डॅशबोर्ड पहा →', gu: 'સંપૂર્ણ ડૅશબોર્ડ જુઓ →' },
}

export const SUPPORTED_LANGUAGES: Language[] = [
  { code: 'en', name: 'English',   native: 'English'    },
  { code: 'hi', name: 'Hindi',     native: 'हिन्दी'     },
  { code: 'bn', name: 'Bengali',   native: 'বাংলা'       },
  { code: 'or', name: 'Odia',      native: 'ଓଡ଼ିଆ'      },
  { code: 'as', name: 'Assamese',  native: 'অসমীয়া'     },
  { code: 'te', name: 'Telugu',    native: 'తెలుగు'      },
  { code: 'ta', name: 'Tamil',     native: 'தமிழ்'       },
  { code: 'mr', name: 'Marathi',   native: 'मराठी'       },
  { code: 'gu', name: 'Gujarati',  native: 'ગુજરાતી'     },
]

// Detect browser language and map to supported code
function detectBrowserLang(): string {
  if (typeof navigator === 'undefined') return 'en'
  const nav = navigator.language || (navigator as any).userLanguage || 'en'
  const code = nav.split('-')[0].toLowerCase()
  const supported = SUPPORTED_LANGUAGES.map(l => l.code)
  // Special mapping
  const map: Record<string, string> = { 'od': 'or', 'odia': 'or' }
  return supported.includes(code) ? code : (map[code] || 'en')
}

const STORAGE_KEY = 'flood_lang'

export function useTranslation() {
  const [lang, setLangState] = useState<string>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) || detectBrowserLang()
    } catch {
      return 'en'
    }
  })

  const setLang = useCallback((code: string) => {
    setLangState(code)
    try { localStorage.setItem(STORAGE_KEY, code) } catch {}
  }, [])

  const t = useCallback((key: string): string => {
    const entry = TRANSLATIONS[key]
    if (!entry) return key
    return entry[lang] || entry['en'] || key
  }, [lang])

  return { t, lang, setLang, languages: SUPPORTED_LANGUAGES }
}
