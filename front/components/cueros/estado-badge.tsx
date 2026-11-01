import { Badge } from "@/components/ui";
import { estadoLabel, estadoTone } from "@/lib/cueros";

export function EstadoBadge({ estado }: { estado: string }) {
  return <Badge tone={estadoTone(estado)}>{estadoLabel(estado)}</Badge>;
}
