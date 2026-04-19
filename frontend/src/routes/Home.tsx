import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LanguagePicker from "../components/LanguagePicker";
import { useCaptureStore } from "../lib/store";

const ITEM_TYPES = [
  { key: "ring",    emoji: "💍", label: "Ring" },
  { key: "chain",   emoji: "⛓️",  label: "Chain" },
  { key: "bangle",  emoji: "🔱", label: "Bangle" },
  { key: "earring", emoji: "✨", label: "Earring" },
  { key: "pendant", emoji: "🔶", label: "Pendant" },
  { key: "coin",    emoji: "🪙", label: "Coin" },
];

export default function Home() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { itemType, setItemType, reset } = useCaptureStore();

  const handleStart = () => {
    reset();
    navigate("/onboarding");
  };

  return (
    <div className="min-h-screen bg-ivory flex flex-col p-6 max-w-lg mx-auto">
      <div className="flex justify-end"><LanguagePicker /></div>

      {/* Hero */}
      <div className="flex flex-col items-center text-center gap-4 mt-6">
        <div className="w-20 h-20 rounded-full bg-gold flex items-center justify-center shadow-lg text-3xl">⚜</div>
        <h1 className="text-4xl font-headline text-brown font-bold">Aurum</h1>
        <p className="text-brown/60 text-base max-w-xs">
          {t("home.tagline")}
        </p>
      </div>

      {/* Item type picker */}
      <div className="mt-8">
        <p className="text-xs text-brown/50 font-medium mb-3 uppercase tracking-wide">What are you bringing?</p>
        <div className="grid grid-cols-3 gap-3">
          {ITEM_TYPES.map((item) => (
            <button
              key={item.key}
              onClick={() => setItemType(item.key)}
              className={`min-touch rounded-xl py-3 flex flex-col items-center gap-1 border transition-all ${
                itemType === item.key
                  ? "border-gold bg-gold/10 shadow-sm"
                  : "border-brown/10 bg-white hover:border-gold/50"
              }`}
            >
              <span className="text-2xl">{item.emoji}</span>
              <span className="text-xs font-medium text-brown/70">{item.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* CTAs */}
      <div className="flex flex-col gap-3 mt-8">
        <button onClick={handleStart}
          className="min-touch w-full bg-gold text-brown-dark font-semibold rounded-xl py-4 text-lg shadow-md hover:bg-gold-dark transition-colors">
          {t("home.start")} →
        </button>
        <button onClick={() => navigate("/result/demo-genuine-22k-chain")}
          className="min-touch w-full border border-brown/15 rounded-xl py-3 text-brown/50 text-sm hover:border-brown/30 transition-colors">
          {t("home.demo")}
        </button>
      </div>

      {/* Footer */}
      <div className="flex justify-center gap-6 mt-auto pt-8 text-sm text-brown/30">
        <button onClick={() => navigate("/lender")} className="hover:text-brown transition-colors">NBFC Dashboard</button>
        <button onClick={() => navigate("/about")} className="hover:text-brown transition-colors">How It Works</button>
      </div>
    </div>
  );
}
