import { Badge } from "./ui";

/** Compact list of warnings coming from the API (already written in Spanish). */
export function Avisos({
  avisos,
  limit = 1,
  wrap = false,
}: {
  avisos: string[];
  limit?: number;
  /** Show the whole text of a long warning on several lines (the tooltip is not the only place). */
  wrap?: boolean;
}) {
  if (avisos.length === 0) return <span className="text-muted">—</span>;
  const visible = avisos.slice(0, limit);
  const hidden = avisos.length - visible.length;
  return (
    <span className="flex max-w-xs flex-wrap gap-1.5">
      {visible.map((aviso) => (
        <Badge key={aviso} tone="warn" title={avisos.join("\n")} wrap={wrap}>
          {aviso}
        </Badge>
      ))}
      {hidden > 0 ? (
        <Badge tone="neutral" title={avisos.join("\n")}>
          +{hidden}
        </Badge>
      ) : null}
    </span>
  );
}
