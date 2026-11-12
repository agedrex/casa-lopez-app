"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ADMIN_GROUPS } from "./sections";

const TABS = [
  { href: "/admin", title: "Resumen" },
  ...ADMIN_GROUPS.flatMap((group) => group.sections),
];

/** Sub-navigation shared by every page under /admin: a scrollable tab strip, one tab per area. */
export function AdminNav() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="Secciones de administración"
      className="-mx-4 mb-6 overflow-x-auto overscroll-x-contain border-b border-line px-4 sm:mx-0 sm:mb-8 sm:px-0"
    >
      <ul className="flex min-w-max gap-1">
        {TABS.map((tab) => {
          const active =
            tab.href === "/admin"
              ? pathname === "/admin"
              : pathname === tab.href || pathname.startsWith(`${tab.href}/`);
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={`-mb-px flex min-h-11 items-center whitespace-nowrap border-b-2 px-3 text-sm transition-colors ${
                  active
                    ? "border-gold text-ink"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {tab.title}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
