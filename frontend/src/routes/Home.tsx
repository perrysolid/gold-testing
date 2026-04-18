import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LanguagePicker from "../components/LanguagePicker";

export default function Home() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="min-h-screen bg-ivory flex flex-col items-center justify-between p-6">
      {/* Language picker */}
      <div className="w-full flex justify-end">
        <LanguagePicker />
      </div>

      {/* Hero */}
      <div className="flex flex-col items-center text-center flex-1 justify-center gap-6">
        {/* Logo mark */}
        <div className="w-20 h-20 rounded-full bg-gold flex items-center justify-center shadow-lg">
          <span className="text-3xl">⚜</span>
        </div>

        <h1 className="text-4xl font-headline text-brown font-bold">Aurum</h1>
        <p className="text-brown/70 text-lg max-w-xs">
          {t("home.tagline", "AI-powered gold assessment for smarter lending")}
        </p>

        {/* CTA */}
        <button
          onClick={() => navigate("/onboarding")}
          className="min-touch w-full max-w-xs bg-gold text-brown-dark font-semibold rounded-xl py-4 text-lg shadow-md hover:bg-gold-dark transition-colors"
        >
          {t("home.start", "Check My Gold")}
        </button>

        {/* Demo shortcut */}
        <button
          onClick={() => navigate("/result/demo-genuine-22k-chain")}
          className="min-touch text-brown/50 text-sm underline underline-offset-4"
        >
          {t("home.demo", "Try demo (no camera needed)")}
        </button>
      </div>

      {/* Footer nav */}
      <div className="flex gap-6 text-sm text-brown/40">
        <button onClick={() => navigate("/lender")} className="hover:text-brown transition-colors">
          NBFC Dashboard
        </button>
        <button onClick={() => navigate("/about")} className="hover:text-brown transition-colors">
          How It Works
        </button>
      </div>
    </div>
  );
}
