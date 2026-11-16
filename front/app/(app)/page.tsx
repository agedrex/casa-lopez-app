import { redirect } from "next/navigation";

// The Panel now lives in Negocio y Administración (first tab); "/" only forwards there.
export default function HomePage() {
  redirect("/admin/panel");
}
