"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { NAV_ITEMS, type NavGroup, type NavItem } from "@/lib/nav";
import { ICONS, Icon } from "./nav-icons";

/** Every path prefix that keeps an item highlighted: its own (activePrefix or href) plus the extra ones. */
function prefixes(item: NavItem): string[] {
  return [item.activePrefix ?? item.href, ...(item.alsoActiveOn ?? [])].map(
    (prefix) => prefix.split("?")[0],
  );
}

const underPrefix = (pathname: string, prefix: string) =>
  pathname === prefix || pathname.startsWith(`${prefix}/`);

/** `items` are the entries the user can see; without them, the full admin menu. */
export function isActive(
  pathname: string,
  href: string,
  items: NavItem[] = NAV_ITEMS.flatMap((group) => group.items),
) {
  const activeHref = items
    .map((item) => ({
      href: item.href,
      length: Math.max(
        -1,
        ...prefixes(item)
          .filter((prefix) => underPrefix(pathname, prefix))
          .map((prefix) => prefix.length),
      ),
    }))
    .filter((item) => item.length >= 0)
    .sort((a, b) => b.length - a.length)[0]?.href;
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
    const [path, query = ""] = (item.activePrefix ?? item.href).split("?");
    const wanted = [...new URLSearchParams(query)];
    const candidates = [
      ...(underPrefix(pathname, path) &&
      !wanted.some(([key, value]) => search.get(key) !== value)
        ? [{ path, wanted: wanted.length }]
        : []),
      ...(item.alsoActiveOn ?? [])
        .filter((extra) => underPrefix(pathname, extra))
        .map((extra) => ({ path: extra, wanted: 0 })),
    ];
    for (const candidate of candidates) {
      const score = candidate.path.length * 10 + candidate.wanted;
      if (!best || score > best.score) best = { href: item.href, score };
    }
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
