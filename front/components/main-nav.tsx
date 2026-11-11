"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
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

/** The rendered item that matches the page best; an href with a query (a filter) also needs its params to match. */
function activeSidebarHref(
  groups: NavGroup[],
  pathname: string,
  search: URLSearchParams,
) {
  let best: { href: string; score: number } | null = null;
  for (const item of groups.flatMap((group) => group.items)) {
    const [path, query = ""] = item.href.split("?");
    if (pathname !== path && !pathname.startsWith(`${path}/`)) continue;
    const wanted = [...new URLSearchParams(query)];
    if (wanted.some(([key, value]) => search.get(key) !== value)) continue;
    const score = path.length * 10 + wanted.length;
    if (!best || score > best.score) best = { href: item.href, score };
  }
  return best?.href;
}

/** Desktop sidebar. On small screens the bottom bar (MobileNav) takes over. */
export function MainNav({ groups }: { groups: NavGroup[] }) {
  const pathname = usePathname();
  const search = useSearchParams();
  const activeHref = activeSidebarHref(groups, pathname, search);
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
            const active = item.href === activeHref;
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
                  path={ICONS[item.icon ?? item.href] ?? ICONS.more}
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
