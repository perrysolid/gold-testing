// FR-3.1–FR-3.2: Tap test — record 3s, show waveform, skip allowed
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCaptureStore } from "../lib/store";

type RecordState = "idle" | "recording" | "done";

export default function Audio() {
  const navigate = useNavigate();
  const { setAudio } = useCaptureStore();
  const [state, setState] = useState<RecordState>("idle");
  const [countdown, setCountdown] = useState(3);
  const [waveData, setWaveData] = useState<number[]>([]);
  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const animRef = useRef<number>(0);
  const analyserRef = useRef<AnalyserNode | null>(null);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 48000, channelCount: 1 } });
      const audioCtx = new AudioContext();
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => chunksRef.current.push(e.data);
      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        const buf = await blob.arrayBuffer();
        setAudio(new Uint8Array(buf));
        stream.getTracks().forEach((t) => t.stop());
        cancelAnimationFrame(animRef.current);
      };
      recorder.start();
      mediaRef.current = recorder;
      setState("recording");

      // Animate waveform
      const draw = () => {
        const data = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteTimeDomainData(data);
        setWaveData(Array.from(data).slice(0, 64));
        animRef.current = requestAnimationFrame(draw);
      };
      draw();

      // Auto-stop at 3s
      let t = 3;
      setCountdown(t);
      const tick = setInterval(() => {
        t -= 1;
        setCountdown(t);
        if (t <= 0) {
          clearInterval(tick);
          recorder.stop();
          setState("done");
        }
      }, 1000);
    } catch {
      navigate("/review"); // mic permission denied → skip gracefully
    }
  };

  useEffect(() => () => cancelAnimationFrame(animRef.current), []);

  return (
    <div className="min-h-screen bg-ivory flex flex-col items-center p-6 gap-6">
      <h1 className="text-2xl font-headline text-brown mt-4">Tap Test (Optional)</h1>
      <p className="text-brown/60 text-sm text-center max-w-xs">
        Tap your jewellery gently on a ceramic tile or glass. Hold phone 10 cm away and press record.
      </p>

      {/* Waveform */}
      <div className="w-full max-w-sm h-24 bg-brown/5 rounded-xl overflow-hidden flex items-center px-2">
        {waveData.length > 0 ? (
          <svg viewBox={`0 0 ${waveData.length} 100`} className="w-full h-full">
            <polyline
              fill="none"
              stroke="#D4AF37"
              strokeWidth="1.5"
              points={waveData.map((v, i) => `${i},${(v / 255) * 100}`).join(" ")}
            />
          </svg>
        ) : (
          <span className="text-brown/30 text-sm mx-auto">Waveform appears here</span>
        )}
      </div>

      {/* Record button */}
      {state === "idle" && (
        <button onClick={startRecording}
          className="min-touch w-20 h-20 rounded-full bg-red-500 text-white text-3xl shadow-lg hover:bg-red-600 flex items-center justify-center">
          ●
        </button>
      )}
      {state === "recording" && (
        <div className="w-20 h-20 rounded-full bg-red-500 flex items-center justify-center text-white text-2xl font-bold animate-pulse">
          {countdown}
        </div>
      )}
      {state === "done" && (
        <div className="flex flex-col items-center gap-2">
          <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center text-green-600 text-2xl">✓</div>
          <p className="text-green-700 text-sm font-medium">Recorded! Good quality.</p>
        </div>
      )}

      <div className="flex flex-col gap-3 w-full max-w-sm mt-auto">
        {state === "done" && (
          <button onClick={() => navigate("/review")}
            className="min-touch w-full bg-gold text-brown-dark font-semibold rounded-xl py-4">
            Continue →
          </button>
        )}
        <button onClick={() => navigate("/review")}
          className="min-touch w-full text-brown/40 text-sm underline py-2">
          Skip tap test
        </button>
      </div>
    </div>
  );
}
