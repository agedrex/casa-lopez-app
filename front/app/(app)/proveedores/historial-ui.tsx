import { Badge } from "@/components/ui";
import { variationText } from "@/lib/proveedores";

/** A bar as long as the API says (0 to 100). The number next to it is the real value; the bar only helps to compare. */
export function MiniBar({ pct, label }: { pct: number | null; label: string }) {
  if (pct === null) return <span className="text-muted">—</span>;
  return (
    <span
      role="img"
      aria-label={`${label}: ${pct} % del máximo`}
      className="inline-block h-2 w-24 overflow-hidden rounded-full bg-parchment align-middle"
    >
      <span
        className="block h-full rounded-full bg-gold"
        style={{ width: `${pct}%` }}
      />
    </span>
  );
}

/** The change against the previous price. A big jump (more than 50 %) is flagged. */
export function VariationBadge({
  value,
  bigJump = false,
}: {
  value: string | null;
  bigJump?: boolean;
}) {
  if (value === null) return <span className="text-muted">—</span>;
  return (
    <Badge
      tone={bigJump ? "warn" : "neutral"}
      title={bigJump ? "Varía mucho respecto del precio anterior." : undefined}
    >
      {variationText(value)}
    </Badge>
  );
}
