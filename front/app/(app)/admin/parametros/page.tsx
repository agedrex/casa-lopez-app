import { redirect } from "next/navigation";

// The Parámetros screen was removed from the UI. The values stay in the database and the
// engine keeps reading them; this only keeps old links (alerts, bookmarks) from breaking.
export default function ParametrosPage() {
  redirect("/admin/usuarios");
}
