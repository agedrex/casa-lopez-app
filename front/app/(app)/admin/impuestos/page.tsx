import { redirect } from "next/navigation";

// Impuestos moved to Costos variables: this path only forwards (old links, e.g. the IIBB warning of the scenarios).
export default function ImpuestosPage() {
  redirect("/costos-fijos/impuestos");
}
