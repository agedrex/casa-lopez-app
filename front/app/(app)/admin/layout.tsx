import { hasRole } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import { AdminNav } from "./admin-nav";

// Every admin page is checked on its own (requireRole) and by proxy.ts; this layout only gives them one frame.
// A gerente only reaches the Panel here, so the tabs of the other areas are not shown to them.
export default async function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user } = await requireSession();
  return (
    <>
      {hasRole(user.role, "admin") ? <AdminNav /> : null}
      {children}
    </>
  );
}
