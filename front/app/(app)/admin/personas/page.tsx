import { redirect } from "next/navigation";

// People are managed in Costos fijos > Mano de obra; this keeps old links working.
export default function PersonasMovedPage() {
  redirect("/costos-fijos?bloque=personal");
}
