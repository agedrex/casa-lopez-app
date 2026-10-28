import { Suspense } from "react";
import { MainNav } from "@/components/main-nav";
import { MobileNav } from "@/components/mobile-nav";
import { UserMenu } from "@/components/user-menu";
import { Wordmark } from "@/components/wordmark";
import { NAV_ITEMS } from "@/lib/nav";
import { hasRole, parseRoles, ROLE_LABELS } from "@/lib/permissions";
import { requireSession } from "@/lib/session";

// The session is request-time data: everything that depends on it streams in
// behind this boundary while the static frame renders immediately.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<p className="p-10 text-sm text-muted">Cargando…</p>}>
      <AuthenticatedShell>{children}</AuthenticatedShell>
    </Suspense>
  );
}

async function AuthenticatedShell({ children }: { children: React.ReactNode }) {
  const { user } = await requireSession();
  const isAdmin = hasRole(user.role, "admin");
  const items = NAV_ITEMS.filter((item) => !item.adminOnly || isAdmin);
  const [role] = parseRoles(user.role);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-surface px-4 py-2 pt-[max(0.5rem,env(safe-area-inset-top))] sm:px-8 sm:py-3">
        <Wordmark />
        <UserMenu
          name={user.name}
          email={user.email}
          roleLabel={role ? ROLE_LABELS[role] : "Sin rol"}
        />
      </header>
      <div className="lg:grid lg:grid-cols-[16rem_1fr]">
        <aside className="hidden border-r border-line bg-surface lg:block lg:min-h-[calc(100vh-4.5rem)]">
          <MainNav items={items} />
        </aside>
        <main className="min-w-0 px-4 pb-[calc(5.5rem+env(safe-area-inset-bottom))] pt-6 sm:px-10 sm:py-10 lg:px-14 lg:pb-10">
          {children}
        </main>
      </div>
      <MobileNav items={items} />
    </div>
  );
}
