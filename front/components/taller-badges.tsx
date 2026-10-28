import type { Taller } from "@/lib/types";
import { Badge } from "./ui";

export function TallerBadges({
  taller,
}: {
  taller: Pick<Taller, "ejemplo" | "activo">;
}) {
  return (
    <span className="inline-flex flex-wrap gap-1.5">
      {taller.ejemplo ? (
        <Badge
          tone="warn"
          title="Taller de ejemplo: reemplazar por el real antes de usarlo"
        >
          Taller de ejemplo
        </Badge>
      ) : null}
      {taller.activo ? null : <Badge tone="neutral">Inactivo</Badge>}
    </span>
  );
}
