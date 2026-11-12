import { redirect } from "next/navigation";

// Models moved to Productos; this keeps old links working.
export default function NuevoModeloMovedPage() {
  redirect("/productos/modelos/nuevo");
}
