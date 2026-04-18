import { useTranslation } from "react-i18next";

const LANGS = [
  { code: "en", label: "EN" },
  { code: "hi", label: "हि" },
];

export default function LanguagePicker() {
  const { i18n } = useTranslation();
  return (
    <div className="flex gap-1">
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => i18n.changeLanguage(l.code)}
          className={`min-touch px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
            i18n.language === l.code
              ? "bg-gold text-brown-dark"
              : "text-brown/40 hover:text-brown"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
