import { redirect } from "next/navigation";

// The Panel now lives in Administración (first tab); "/" only forwards there.
export default function HomePage() {
  redirect("/admin/panel");
}
