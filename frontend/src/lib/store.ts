import { create } from "zustand";

type CaptureKind = "image_top" | "image_side" | "image_hallmark";

interface CaptureStore {
  itemType: string;
  captures: Partial<Record<CaptureKind, Uint8Array>>;
  audio: Uint8Array | null;
  assessmentId: string | null;

  setItemType: (t: string) => void;
  setCaptures: (kind: CaptureKind, data: Uint8Array) => void;
  setAudio: (data: Uint8Array) => void;
  setAssessmentId: (id: string) => void;
  reset: () => void;
}

export const useCaptureStore = create<CaptureStore>((set) => ({
  itemType: "ring",
  captures: {},
  audio: null,
  assessmentId: null,

  setItemType: (t) => set({ itemType: t }),
  setCaptures: (kind, data) =>
    set((s) => ({ captures: { ...s.captures, [kind]: data } })),
  setAudio: (data) => set({ audio: data }),
  setAssessmentId: (id) => set({ assessmentId: id }),
  reset: () => set({ captures: {}, audio: null, assessmentId: null }),
}));
