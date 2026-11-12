import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { Suspense } from "react";
import { MainNav } from "@/components/main-nav";
import { MobileNav } from "@/components/mobile-nav";
import { UserMenu } from "@/components/user-menu";
import { VozButton } from "@/components/voz-button";
import { Wordmark } from "@/components/wordmark";
import { desktopNavForRole, mobileTabs, navForRole } from "@/lib/nav";
import {
  canAccessPath,
  canUseVoice,
  canWrite,
  homePath,
  parseRoles,
  ROLE_LABELS,
  ROLES,
} from "@/lib/permissions";
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
  const { user, previewAvailable } = await requireSession();
  // Second check after the proxy: deny by default, and send the role to its own home.
  if (
    !canAccessPath(user.role, (await headers()).get("x-app-pathname") ?? "")
  ) {
    redirect(homePath(user.role));
  }
  const roles = parseRoles(user.role);
  const isAdmin = roles.includes("admin");
  const [role] = roles;
  const groups = navForRole(roles);
  const tabs = mobileTabs(groups, roles);

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b border-line bg-surface px-4 py-2 pt-[max(0.5rem,env(safe-area-inset-top))] sm:px-8 sm:py-3">
        <Wordmark />
        <div className="flex items-center gap-2">
          {canUseVoice(user.role) ? <VozButton /> : null}
          <UserMenu
            name={user.name}
            email={user.email}
            roleLabel={role ? ROLE_LABELS[role] : "Sin rol"}
            previewRoles={
              previewAvailable
                ? ROLES.map((value) => ({ value, label: ROLE_LABELS[value] }))
                : undefined
            }
            currentRole={role}
          />
        </div>
      </header>
      <div className="lg:grid lg:grid-cols-[16rem_1fr]">
        <aside className="hidden border-r border-line bg-surface lg:block lg:min-h-[calc(100vh-4.5rem)]">
          <MainNav groups={desktopNavForRole(roles)} />
        </aside>
        <main className="min-w-0 px-4 pb-[calc(5.5rem+env(safe-area-inset-bottom))] pt-6 sm:px-10 sm:py-10 lg:px-14 lg:pb-10">
          {children}
        </main>
      </div>
      <MobileNav
        groups={groups}
        tabs={tabs}
        canCreate={canWrite(user.role) || roles.includes("taller")}
        restricted={!isAdmin}
      />
    </div>
  );
}
