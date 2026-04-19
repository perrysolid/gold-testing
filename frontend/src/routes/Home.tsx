import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useCaptureStore } from "../lib/store";
import HallmarkGuide from "../components/HallmarkGuide";

const ITEM_TYPES = [
  { key: "ring",    emoji: "💍" },
  { key: "chain",   emoji: "⛓️" },
  { key: "bangle",  emoji: "🔱" },
  { key: "earring", emoji: "✨" },
  { key: "pendant", emoji: "🔶" },
  { key: "coin",    emoji: "🪙" },
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
      {/* Hero */}
      <div className="flex flex-col items-center text-center gap-4 mt-6">
        <div className="w-20 h-20 rounded-full bg-gold flex items-center justify-center shadow-lg text-3xl">⚜</div>
        <h1 className="text-4xl font-headline text-brown font-bold">Aurum</h1>
        <p className="text-brown/60 text-base max-w-xs">
          {t("home.tagline")}
        </p>
      </div>

      {/* How it works */}
      <div className="mt-6 rounded-xl bg-white shadow-sm p-4">
        <p className="text-xs text-brown/50 font-medium mb-3 uppercase tracking-wide">{t("home.how")}</p>
        <div className="flex flex-col gap-2 text-sm text-brown/70">
          <p>1. {t("home.how_step1")}</p>
          <p>2. {t("home.how_step2")}</p>
          <p>3. {t("home.how_step3")}</p>
        </div>
      </div>

      {/* Item type picker */}
      <div className="mt-6">
        <p className="text-xs text-brown/50 font-medium mb-3 uppercase tracking-wide">{t("home.what")}</p>
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
              <span className="text-xs font-medium text-brown/70">{t(`items.${item.key}`)}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Hallmark guide */}
      <div className="mt-5">
        <HallmarkGuide />
      </div>

      {/* CTAs */}
      <div className="flex flex-col gap-3 mt-6">
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
        <button onClick={() => navigate("/lender")} className="hover:text-brown transition-colors">{t("home.dashboard")}</button>
        <button onClick={() => navigate("/about")} className="hover:text-brown transition-colors">{t("home.how")}</button>
      </div>
    </div>
  );
}
