// TODO [FR-4]: Self-declared data form + submit to /assess/submit
import { useNavigate } from "react-router-dom";

export default function Review() {
  const navigate = useNavigate();
  const handleSubmit = () => navigate("/result/demo-genuine-22k-chain");

  return (
    <div className="min-h-screen bg-ivory flex flex-col p-6 gap-6 max-w-lg mx-auto">
      <h2 className="text-2xl font-headline text-brown">Review &amp; Submit</h2>
      <div className="rounded-xl bg-white shadow-sm p-4 flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-sm text-brown/60 font-medium">Declared Weight (g)</span>
          <input type="number" placeholder="e.g. 10" className="border border-brown/20 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-gold" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-brown/60 font-medium">Karat / Stamp</span>
          <input type="text" placeholder="e.g. 916, 22K, BIS" className="border border-brown/20 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-gold" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm text-brown/60 font-medium">Notes (optional)</span>
          <textarea placeholder="e.g. gifted from mother, 10 years old" className="border border-brown/20 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-gold resize-none h-20" />
        </label>
      </div>
      <button
        onClick={handleSubmit}
        className="min-touch w-full bg-brown text-ivory font-semibold rounded-xl py-4 text-lg shadow-md hover:bg-brown-dark transition-colors"
      >
        Submit for Estimate
      </button>
    </div>
  );
}
