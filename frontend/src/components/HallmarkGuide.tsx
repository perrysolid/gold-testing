// Collapsible hallmark education card — shown on Capture (hallmark step) and Result screen
import { useState } from "react";
import { useTranslation } from "react-i18next";

const PURITIES = [
  { mark: "999", karat: "24K", pct: "99.9%", use: "Coins & investment bars — very soft, rarely worn" },
  { mark: "916", karat: "22K", pct: "91.6%", use: "Most Indian jewellery — necklaces, chains, bangles" },
  { mark: "750", karat: "18K", pct: "75%",   use: "Rings & studded jewellery — harder, holds stones well" },
  { mark: "585", karat: "14K", pct: "58.5%", use: "Durable everyday wear — common in international jewellery" },
  { mark: "375", karat: "9K",  pct: "37.5%", use: "Budget jewellery — lowest gold content in BIS system" },
];

const PURITY_MARKS_HI: Record<string, string> = {
  "999": "सिक्के और निवेश बार — बहुत नरम",
  "916": "अधिकांश भारतीय गहने — हार, चेन, कंगन",
  "750": "अंगूठियां और जड़ाऊ गहने — मज़बूत",
  "585": "टिकाऊ रोज़ाना पहनने के गहने",
  "375": "बजट गहने — सबसे कम सोना",
};

export default function HallmarkGuide({ compact = false }: { compact?: boolean }) {
  const { i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const isHi = i18n.language === "hi";

  return (
    <div className="rounded-xl bg-gold/8 border border-gold/20 overflow-hidden">
      {/* Toggle header */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex items-center gap-2">
          <span className="text-gold text-lg">⚜</span>
          <span className="text-sm font-semibold text-brown">
            {isHi ? "हॉलमार्क क्या है?" : "What is a Hallmark?"}
          </span>
        </div>
        <span className="text-brown/40 text-sm">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="px-4 pb-4 flex flex-col gap-4 border-t border-gold/15">

          {/* BIS explanation */}
          <div className="pt-3">
            <p className="text-xs font-bold text-brown/50 uppercase tracking-wide mb-1">
              {isHi ? "BIS हॉलमार्क क्या है?" : "What is BIS Hallmark?"}
            </p>
            <p className="text-sm text-brown/70 leading-relaxed">
              {isHi
                ? "BIS (भारतीय मानक ब्यूरो) भारत सरकार की संस्था है जो सोने की शुद्धता की गारंटी देती है। BIS हॉलमार्क का मतलब है कि सरकार ने इस सोने की जांच की है। बिना हॉलमार्क के सोने की शुद्धता का पता नहीं चल सकता।"
                : "BIS (Bureau of Indian Standards) is India's government authority that guarantees gold purity. A BIS hallmark means the government has certified this gold. Without a hallmark, there's no way to verify purity."}
            </p>
          </div>

          {/* Purity table */}
          <div>
            <p className="text-xs font-bold text-brown/50 uppercase tracking-wide mb-2">
              {isHi ? "शुद्धता के निशान" : "Purity Marks — What the Numbers Mean"}
            </p>
            <div className="flex flex-col gap-1.5">
              {PURITIES.map((p) => (
                <div key={p.mark} className="flex items-start gap-3 bg-white/60 rounded-lg px-3 py-2">
                  <div className="shrink-0 text-center">
                    <span className="block text-base font-bold text-brown">{p.mark}</span>
                    <span className="block text-xs font-semibold text-gold">{p.karat}</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-xs font-semibold text-brown/70">{p.pct} {isHi ? "शुद्ध सोना" : "pure gold"}</p>
                    <p className="text-xs text-brown/50 mt-0.5">
                      {isHi ? PURITY_MARKS_HI[p.mark] : p.use}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* HUID explanation */}
          <div className="bg-blue-50 rounded-lg px-3 py-2.5">
            <p className="text-xs font-bold text-blue-700 mb-1">
              {isHi ? "HUID क्या है?" : "What is HUID?"}
            </p>
            <p className="text-xs text-blue-700/80 leading-relaxed">
              {isHi
                ? "HUID (Hallmarking Unique ID) एक 6-अंकी कोड है जो 2022 से हर हॉलमार्क वाले गहने पर अनिवार्य है। इससे आप BIS वेबसाइट पर जाकर ज्वेलर की जानकारी जांच सकते हैं।"
                : "HUID (Hallmarking Unique ID) is a 6-character code mandatory since 2022 on every BIS-hallmarked piece. You can verify the jeweller's details on the BIS website using this code."}
            </p>
          </div>

          {/* How to find hallmark */}
          {!compact && (
            <div>
              <p className="text-xs font-bold text-brown/50 uppercase tracking-wide mb-1">
                {isHi ? "हॉलमार्क कहाँ देखें?" : "Where to Find the Hallmark"}
              </p>
              <p className="text-xs text-brown/60 leading-relaxed">
                {isHi
                  ? "अंगूठी की अंदरूनी सतह • चेन के क्लैस्प पर • बाली की पिन पर • बड़े गहनों पर सीधे मुहर लगी होती है। हॉलमार्क में आमतौर पर BIS का त्रिभुज चिह्न, शुद्धता संख्या (जैसे 916) और 6-अंकी HUID होता है।"
                  : "Inside a ring band • On the chain clasp • On earring pins • Stamped directly on larger pieces. Look for the BIS triangle logo, the purity number (e.g. 916), and the 6-character HUID."}
              </p>
            </div>
          )}

        </div>
      )}
    </div>
  );
}
