"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import type { NavItem } from "@/lib/nav";
import { isActive } from "./main-nav";

const ICONS: Record<string, string> = {
  "/": "M4 13h6V4H4v9zm0 7h6v-5H4v5zm8 0h8V11h-8v9zm0-16v5h8V4h-8z",
  "/productos": "M4 7l8-4 8 4-8 4-8-4zm0 4l8 4 8-4M4 15l8 4 8-4",
  "/materiales":
    "M12 3v18M16.5 7.5C16.5 6 14.5 5 12 5S7.5 6 7.5 8s2 2.5 4.5 3 4.5 1 4.5 3-2 3-4.5 3-4.5-1-4.5-2.5",
  "/fabricacion": "M3 20h18M5 20V9l5 3V9l5 3V5h4v15",
  more: "M5 12h.01M12 12h.01M19 12h.01",
};

function Icon({ path }: { path: string }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="size-6"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={path} />
    </svg>
  );
}

const tabClass = (active: boolean) =>
  `flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 px-1 text-[0.6875rem] ${
    active ? "text-ink" : "text-muted"
  }`;

/** Bottom tab bar for phones: four main sections plus a "Más" sheet. */
export function MobileNav({ items }: { items: NavItem[] }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const primary = items.filter((item) => item.primary);
  const more = items.filter((item) => !item.primary);
  const moreActive = more.some((item) => isActive(pathname, item.href));

  // Close the sheet whenever the route changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: pathname is the trigger
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <div className="lg:hidden">
      {open ? (
        <>
          <button
            type="button"
            aria-label="Cerrar menú"
            onClick={() => setOpen(false)}
            className="fixed inset-0 z-30 bg-ink/40"
          />
          <div
            id="mas-secciones"
            className="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] z-40 max-h-[70dvh] overflow-y-auto rounded-t-2xl border-t border-line bg-surface p-3 shadow-card"
          >
            <ul>
              {more.map((item) => {
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`flex min-h-12 items-center rounded-card px-4 text-base ${
                        active ? "bg-ink text-white" : "text-ink-soft"
                      }`}
                    >
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </>
      ) : null}
      <nav
        aria-label="Secciones"
        className="fixed inset-x-0 bottom-0 z-50 flex border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]"
      >
        {primary.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={tabClass(active)}
            >
              <Icon path={ICONS[item.href] ?? ICONS.more} />
              <span>{item.shortLabel ?? item.label}</span>
            </Link>
          );
        })}
        {more.length > 0 ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls="mas-secciones"
            onClick={() => setOpen((value) => !value)}
            className={tabClass(open || moreActive)}
          >
            <Icon path={ICONS.more} />
            <span>Más</span>
          </button>
        ) : null}
      </nav>
    </div>
  );
}
