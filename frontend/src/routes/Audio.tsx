// TODO [FR-3.1–FR-3.4]: Tap test recording + waveform preview
import { useNavigate } from "react-router-dom";

export default function Audio() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-ivory flex flex-col items-center justify-center p-6 gap-6">
      <h2 className="text-2xl font-headline text-brown">Optional Tap Test</h2>
      <p className="text-brown/60 text-center max-w-xs">
        Tap your jewellery gently against a hard surface and record 3 seconds of sound.
      </p>
      <div className="w-full max-w-sm h-24 rounded-xl bg-brown/10 flex items-center justify-center border-2 border-dashed border-brown/30">
        <span className="text-brown/40 text-sm">Waveform (FR-3)</span>
      </div>
      <button
        onClick={() => navigate("/review")}
        className="min-touch w-full max-w-sm bg-gold text-brown-dark font-semibold rounded-xl py-4"
      >
        Record &amp; Continue
      </button>
      <button onClick={() => navigate("/review")} className="text-brown/40 text-sm underline">
        Skip
      </button>
    </div>
  );
}
