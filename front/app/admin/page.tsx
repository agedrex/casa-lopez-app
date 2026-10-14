import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { connection } from "next/server";
import { LogoutButton } from "@/app/admin/logout-button";
import { requireAdminSession } from "@/lib/admin-auth";
import { fetchAdminStatus } from "@/lib/admin-status";

export default async function AdminPage() {
  await connection();
  const sessionHeaders = await headers();
  const session = await requireAdminSession(sessionHeaders);
  if (!session) redirect("/login?next=%2Fadmin");
  const adminStatus = await fetchAdminStatus({
    backendUrl: process.env.AUTH_BACKEND_URL,
    cookie: sessionHeaders.get("cookie"),
    expectedUserId: session.user?.id,
  });

  if (!adminStatus) {
    return (
      <main>
        <section aria-labelledby="admin-unavailable-title">
          <h1 id="admin-unavailable-title">Administración no disponible</h1>
          <p>No pudimos verificar el acceso. Intentá de nuevo más tarde.</p>
          <LogoutButton />
        </section>
      </main>
    );
  }

  return (
    <main>
      <section aria-labelledby="admin-title">
        <h1 id="admin-title">Administración</h1>
        <p>Sesión iniciada como {session.user?.email ?? session.user?.id}.</p>
        <p>Verificación administrativa: activa.</p>
        <LogoutButton />
      </section>
    </main>
  );
}
