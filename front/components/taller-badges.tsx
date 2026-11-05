import type { Taller } from "@/lib/types";
import { Badge } from "./ui";

export function TallerBadges({ taller }: { taller: Pick<Taller, "activo"> }) {
  return (
    <span className="inline-flex flex-wrap gap-1.5">
      {taller.activo ? null : <Badge tone="neutral">Inactivo</Badge>}
    </span>
  );
}
