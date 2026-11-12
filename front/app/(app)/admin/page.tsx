import { redirect } from "next/navigation";

// The old summary hub is gone: /admin lands on the first tab (Panel) (proxy.ts keeps non-admins out).
export default function AdminPage() {
  redirect("/admin/panel");
}
