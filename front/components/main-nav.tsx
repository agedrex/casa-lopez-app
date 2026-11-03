"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS, type NavGroup } from "@/lib/nav";
import { ICONS, Icon } from "./nav-icons";

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
    <nav aria-label="Secciones" className="flex flex-col gap-5 px-4 py-6">
      {groups.map((group, index) => (
        <section
          key={`${group.title}-${index}`}
          aria-label={group.title || undefined}
          className={`flex flex-col gap-0.5 ${
            index > 0 && !group.title ? "border-t border-line pt-4" : ""
          }`}
        >
          {group.title ? (
            <h2 className="px-3 pb-1 text-xs font-semibold uppercase tracking-caps-sm text-muted">
              {group.title}
            </h2>
          ) : null}
          {group.items.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 whitespace-nowrap rounded-card px-3 py-2 text-sm transition-colors ${
                  active
                    ? "bg-ink text-white"
                    : "text-ink-soft hover:bg-parchment"
                }`}
              >
                <Icon
                  path={ICONS[item.href] ?? ICONS.more}
                  className="size-5 shrink-0"
                />
                {item.label}
              </Link>
            );
          })}
        </section>
      ))}
    </nav>
  );
}
