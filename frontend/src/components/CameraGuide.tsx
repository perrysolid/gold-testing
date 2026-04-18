// TODO [FR-2.1]: Overlay silhouette guide for camera capture
// Placeholder SVG overlay; replace with item-type-specific shapes
type Props = { itemType: string };

export default function CameraGuide({ itemType }: Props) {
  return (
    <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
      <div className="border-2 border-gold border-dashed rounded-full w-48 h-48 opacity-60" />
      <span className="absolute bottom-4 text-gold text-xs font-medium">{itemType} — centre in guide</span>
    </div>
  );
}
