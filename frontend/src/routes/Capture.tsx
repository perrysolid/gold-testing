// TODO [FR-2.1–FR-2.5]: Camera capture with overlay guides + quality chips
// Stub: shows placeholder UI
import { useNavigate } from "react-router-dom";

export default function Capture() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-ivory flex flex-col items-center justify-center p-6 gap-6">
      <h2 className="text-2xl font-headline text-brown">Capture Your Jewellery</h2>
      <div className="w-full max-w-sm h-72 rounded-xl bg-brown/10 flex items-center justify-center border-2 border-dashed border-brown/30">
        <span className="text-brown/40 text-sm">Camera preview (FR-2.1)</span>
      </div>
      <button
        onClick={() => navigate("/audio")}
        className="min-touch w-full max-w-sm bg-gold text-brown-dark font-semibold rounded-xl py-4"
      >
        Continue →
      </button>
    </div>
  );
}
