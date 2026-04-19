// FR-1.1, FR-1.2, FR-1.3: Phone OTP → KYC form → consent → capture
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { api } from "../lib/api";

type Step = "phone" | "otp" | "kyc" | "consent";

const PAN_RE = /^[A-Z]{5}[0-9]{4}[A-Z]$/;

export default function Onboarding() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [otp, setOtp] = useState("");
  const [name, setName] = useState("");
  const [pan, setPan] = useState("");
  const [purpose, setPurpose] = useState("personal_loan");
  const [consentChecked, setConsentChecked] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const sendOtp = async () => {
    if (phone.replace(/\D/g, "").length !== 10) {
      setError("Enter a valid 10-digit mobile number");
      return;
    }
    setLoading(true);
    setError("");
    try {
      await api.post("/auth/otp/send", { phone });
      setStep("otp");
    } catch {
      setError("Could not send OTP. Try again.");
    } finally {
      setLoading(false);
    }
  };

  const verifyOtp = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.post<{ access_token: string }>("/auth/otp/verify", { phone, otp });
      localStorage.setItem("aurum_token", res.access_token);
      setStep("kyc");
    } catch {
      setError("Invalid OTP. Use 123456 for demo.");
    } finally {
      setLoading(false);
    }
  };

  const submitKyc = () => {
    if (!name.trim()) { setError("Name is required"); return; }
    if (pan && !PAN_RE.test(pan.toUpperCase())) { setError("PAN format: ABCDE1234F"); return; }
    setError("");
    setStep("consent");
  };

  const submitConsent = () => {
    if (!consentChecked) { setError("Please accept the declaration"); return; }
    navigate("/capture");
  };

  return (
    <div className="min-h-screen bg-ivory flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-sm flex flex-col gap-6">
        {/* Progress dots */}
        <div className="flex gap-2 justify-center">
          {(["phone", "otp", "kyc", "consent"] as Step[]).map((s) => (
            <div key={s} className={`w-2 h-2 rounded-full ${step === s ? "bg-gold" : "bg-brown/20"}`} />
          ))}
        </div>

        {step === "phone" && (
          <>
            <h1 className="text-2xl font-headline text-brown text-center">{t("onboarding.enter_mobile")}</h1>
            <input
              type="tel"
              inputMode="numeric"
              placeholder="10-digit mobile number"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="border border-brown/20 rounded-xl p-4 text-lg focus:outline-none focus:ring-2 focus:ring-gold"
            />
            <button onClick={sendOtp} disabled={loading}
              className="min-touch bg-gold text-brown-dark font-semibold rounded-xl py-4 disabled:opacity-50">
              {loading ? `${t("common.loading")}` : t("onboarding.send_otp")}
            </button>
          </>
        )}

        {step === "otp" && (
          <>
            <h1 className="text-2xl font-headline text-brown text-center">{t("onboarding.enter_otp")}</h1>
            <p className="text-brown/50 text-sm text-center">Sent to +91 {phone} · Demo OTP: 123456</p>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              placeholder="6-digit OTP"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              className="border border-brown/20 rounded-xl p-4 text-2xl tracking-widest text-center focus:outline-none focus:ring-2 focus:ring-gold"
            />
            <button onClick={verifyOtp} disabled={loading}
              className="min-touch bg-gold text-brown-dark font-semibold rounded-xl py-4 disabled:opacity-50">
              {loading ? `${t("common.loading")}` : t("onboarding.continue")}
            </button>
            <button onClick={() => sendOtp()} className="text-brown/40 text-sm text-center underline">
              {t("onboarding.resend")}
            </button>
          </>
        )}

        {step === "kyc" && (
          <>
            <h1 className="text-2xl font-headline text-brown text-center">{t("onboarding.kyc_title")}</h1>
            <input type="text" placeholder={t("onboarding.name_label") + " *"} value={name}
              onChange={(e) => setName(e.target.value)}
              className="border border-brown/20 rounded-xl p-4 focus:outline-none focus:ring-2 focus:ring-gold" />
            <input type="text" placeholder={t("onboarding.pan_label") + " (optional)"} value={pan}
              onChange={(e) => setPan(e.target.value.toUpperCase())} maxLength={10}
              className="border border-brown/20 rounded-xl p-4 uppercase tracking-wider focus:outline-none focus:ring-2 focus:ring-gold" />
            <select value={purpose} onChange={(e) => setPurpose(e.target.value)}
              className="border border-brown/20 rounded-xl p-4 bg-white focus:outline-none focus:ring-2 focus:ring-gold">
              <option value="personal_loan">Personal Loan</option>
              <option value="business_loan">Business Loan</option>
              <option value="emergency">Emergency Funds</option>
            </select>
            <button onClick={submitKyc}
              className="min-touch bg-gold text-brown-dark font-semibold rounded-xl py-4">
              {t("onboarding.continue")}
            </button>
          </>
        )}

        {step === "consent" && (
          <>
            <h1 className="text-2xl font-headline text-brown text-center">{t("onboarding.consent_title")}</h1>
            <div className="bg-brown/5 rounded-xl p-4 text-sm text-brown/70 leading-relaxed">
              {t("onboarding.consent_body")}
            </div>
            <label className="flex items-start gap-3 cursor-pointer">
              <input type="checkbox" checked={consentChecked}
                onChange={(e) => setConsentChecked(e.target.checked)}
                className="mt-1 w-5 h-5 rounded accent-gold" />
              <span className="text-sm text-brown/70">{t("onboarding.consent_agree")}</span>
            </label>
            <p className="text-xs text-brown/30 text-center">
              Signed at {new Date().toLocaleString("en-IN")}
            </p>
            <button onClick={submitConsent}
              className="min-touch bg-brown text-ivory font-semibold rounded-xl py-4">
              {t("onboarding.continue")}
            </button>
          </>
        )}

        {error && <p className="text-red-600 text-sm text-center">{error}</p>}
      </div>
    </div>
  );
}
