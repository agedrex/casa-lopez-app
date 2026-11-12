import { redirect } from "next/navigation";

// Colors and categories moved to Productos; this keeps old links working.
export default function CatalogosMovedPage() {
  redirect("/productos/catalogos");
}
