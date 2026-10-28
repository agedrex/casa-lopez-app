"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { NavItem } from "@/lib/nav";

export function isActive(pathname: string, href: string) {
  return href === "/"
    ? pathname === "/"
    : pathname === href || pathname.startsWith(`${href}/`);
}

/** Desktop sidebar. On small screens the bottom bar (MobileNav) takes over. */
export function MainNav({ items }: { items: NavItem[] }) {
  const pathname = usePathname();
  return (
    <nav aria-label="Secciones" className="flex flex-col gap-1 px-6 py-8">
      {items.map((item) => {
        const active = isActive(pathname, item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            aria-current={active ? "page" : undefined}
            className={`whitespace-nowrap rounded-card px-3 py-2 text-sm transition-colors ${
              active ? "bg-ink text-white" : "text-ink-soft hover:bg-parchment"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
