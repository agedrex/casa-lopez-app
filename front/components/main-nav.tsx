"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS, type NavGroup } from "@/lib/nav";

export function isActive(pathname: string, href: string) {
  const activeHref = NAV_ITEMS.flatMap((group) => group.items)
    .filter(
      (item) => pathname === item.href || pathname.startsWith(`${item.href}/`),
    )
    .sort((a, b) => b.href.length - a.href.length)[0]?.href;
  return href === activeHref;
}

/** Desktop sidebar. On small screens the bottom bar (MobileNav) takes over. */
export function MainNav({ groups }: { groups: NavGroup[] }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Secciones" className="flex flex-col gap-6 px-6 py-8">
      {groups.map((group) => (
        <section
          key={group.title}
          aria-label={group.title}
          className="flex flex-col gap-1"
        >
          <h2 className="px-3 pb-1 text-xs font-semibold uppercase tracking-caps-sm text-muted">
            {group.title}
          </h2>
          {group.items.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`whitespace-nowrap rounded-card px-3 py-2 text-sm transition-colors ${
                  active
                    ? "bg-ink text-white"
                    : "text-ink-soft hover:bg-parchment"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </section>
      ))}
    </nav>
  );
}
