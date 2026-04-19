// FR-3.1–FR-3.2: Tap test — record 3s, show waveform, skip allowed
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useCaptureStore } from "../lib/store";

type RecordState = "idle" | "recording" | "done";

export default function Audio() {
  const navigate = useNavigate();
  const { t } = useTranslation();
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
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { sampleRate: 16000, channelCount: 1 } });
      const audioCtx = new AudioContext({ sampleRate: 16000 });
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      // Capture raw PCM data
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      const samples: Float32Array[] = [];
      processor.onaudioprocess = (e) => {
        samples.push(new Float32Array(e.inputBuffer.getChannelData(0)));
      };
      source.connect(processor);
      processor.connect(audioCtx.destination);

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
      let sec = 3;
      setCountdown(sec);
      const tick = setInterval(() => {
        sec -= 1;
        setCountdown(sec);
        if (sec <= 0) {
          clearInterval(tick);
          // Stop capturing
          source.disconnect();
          processor.disconnect();
          stream.getTracks().forEach((t) => t.stop());
          audioCtx.close();
          cancelAnimationFrame(animRef.current);

          // Encode to WAV
          const flattened = flattenSamples(samples);
          const wav = encodeWAV(flattened, 16000);
          setAudio(wav);
          setState("done");
        }
      }, 1000);
    } catch {
      navigate("/review"); // mic permission denied → skip gracefully
    }
  };

  const flattenSamples = (chunks: Float32Array[]) => {
    const totalLen = chunks.reduce((acc, c) => acc + c.length, 0);
    const result = new Float32Array(totalLen);
    let offset = 0;
    for (const chunk of chunks) {
      result.set(chunk, offset);
      offset += chunk.length;
    }
    return result;
  };

  const encodeWAV = (samples: Float32Array, sampleRate: number) => {
    const buffer = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(buffer);
    const writeString = (v: DataView, o: number, s: string) => {
      for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i));
    };
    writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + samples.length * 2, true);
    writeString(view, 8, "WAVE");
    writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // Mono
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, "data");
    view.setUint32(40, samples.length * 2, true);
    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Uint8Array(buffer);
  };

  useEffect(() => () => cancelAnimationFrame(animRef.current), []);

  return (
    <div className="min-h-screen bg-ivory flex flex-col items-center p-6 gap-6">
      <h1 className="text-2xl font-headline text-brown mt-4">{t("audio.title")}</h1>
      <p className="text-brown/60 text-sm text-center max-w-xs">
        {t("audio.instruction")}
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
          <span className="text-brown/30 text-sm mx-auto">{t("audio.recording").replace("…", "")}</span>
        )}
      </div>

      {/* Record button */}
      {state === "idle" && (
        <button onClick={startRecording}
          className="min-touch w-20 h-20 rounded-full bg-red-500 text-white text-3xl shadow-lg hover:bg-red-600 flex items-center justify-center">
          ●
        </button>
      )}
      {state === "idle" && (
        <p className="text-brown/40 text-xs">{t("audio.record")}</p>
      )}

      {/* Demo sample audio buttons */}
      {state === "idle" && (
        <div className="flex flex-col gap-2 w-full max-w-sm">
          <p className="text-brown/40 text-xs text-center">— or use a sample —</p>
          <button
            onClick={async () => {
              try {
                const res = await fetch("/demo/audio/tap_solid_22k.wav");
                const buf = await res.arrayBuffer();
                setAudio(new Uint8Array(buf));
                setState("done");
              } catch { /* ignore */ }
            }}
            className="min-touch w-full bg-white/8 border border-gold/30 text-gold/80 rounded-xl py-2.5 text-xs font-medium hover:bg-gold/10 transition-colors"
          >
            ⚡ Sample: solid 22K gold tap
          </button>
          <button
            onClick={async () => {
              try {
                const res = await fetch("/demo/audio/tap_hollow_bangle.wav");
                const buf = await res.arrayBuffer();
                setAudio(new Uint8Array(buf));
                setState("done");
              } catch { /* ignore */ }
            }}
            className="min-touch w-full bg-white/8 border border-gold/30 text-gold/80 rounded-xl py-2.5 text-xs font-medium hover:bg-gold/10 transition-colors"
          >
            ⚡ Sample: hollow bangle tap
          </button>
        </div>
      )}
      {state === "recording" && (
        <div className="flex flex-col items-center gap-2">
          <div className="w-20 h-20 rounded-full bg-red-500 flex items-center justify-center text-white text-2xl font-bold animate-pulse">
            {countdown}
          </div>
          <p className="text-brown/50 text-sm">{t("audio.recording")}</p>
        </div>
      )}
      {state === "done" && (
        <div className="flex flex-col items-center gap-2">
          <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center text-green-600 text-2xl">✓</div>
          <p className="text-green-700 text-sm font-medium">Sound captured</p>
          <p className="text-brown/40 text-xs text-center max-w-xs">
            The tap audio will be analysed together with your photos during assessment.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-3 w-full max-w-sm mt-auto">
        {state === "done" && (
          <button onClick={() => navigate("/review")}
            className="min-touch w-full bg-gold text-brown-dark font-semibold rounded-xl py-4">
            {t("capture.next")} →
          </button>
        )}
        <button onClick={() => navigate("/review")}
          className="min-touch w-full text-brown/40 text-sm underline py-2">
          {t("audio.skip")}
        </button>
      </div>
    </div>
  );
}
