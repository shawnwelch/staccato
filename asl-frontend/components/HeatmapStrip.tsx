export default function HeatmapStrip({
  src,
  alt = "Timeline heat map of cut density",
}: {
  src: string | null;
  alt?: string;
}) {
  if (!src) {
    return (
      <div className="heatmap heatmap-empty" role="img" aria-label={alt}>
        <span>Heat map not available for this analysis</span>
      </div>
    );
  }
  return (
    <div className="heatmap">
      {/* Backend-generated PNG; plain img keeps this a pass-through. */}
      <img src={src} alt={alt} />
    </div>
  );
}
