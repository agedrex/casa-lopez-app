"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export type SectionTab = {
  href: string;
  title: string;
  /** Active only on this exact path (the list page that other tabs live under). */
  exact?: boolean;
};

/** A scrollable tab strip, one tab per area of a section. */
export function SectionTabs({
  label,
  tabs,
}: {
  label: string;
  tabs: SectionTab[];
}) {
  const pathname = usePathname();
  return (
    <nav
      aria-label={label}
      className="-mx-4 mb-6 overflow-x-auto overscroll-x-contain border-b border-line px-4 sm:mx-0 sm:mb-8 sm:px-0"
    >
      <ul className="flex min-w-max gap-1">
        {tabs.map((tab) => {
          const active = tab.exact
            ? pathname === tab.href
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
