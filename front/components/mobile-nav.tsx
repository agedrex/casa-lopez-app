"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import type { NavGroup, NavItem } from "@/lib/nav";
import { isActive } from "./main-nav";

const ICONS: Record<string, string> = {
  "/": "M4 13h6V4H4v9zm0 7h6v-5H4v5zm8 0h8V11h-8v9zm0-16v5h8V4h-8z",
  "/productos": "M4 7l8-4 8 4-8 4-8-4zm0 4l8 4 8-4M4 15l8 4 8-4",
  "/materiales":
    "M12 3v18M16.5 7.5C16.5 6 14.5 5 12 5S7.5 6 7.5 8s2 2.5 4.5 3 4.5 1 4.5 3-2 3-4.5 3-4.5-1-4.5-2.5",
  "/fabricacion": "M3 20h18M5 20V9l5 3V9l5 3V5h4v15",
  "/corte": "M4 4l16 16M20 4L4 20M8 8l2-2M14 18l2-2",
  "/cueros": "M4 7l8-4 8 4v10l-8 4-8-4V7zm0 0l8 4 8-4M12 11v10",
  "/grilla": "M3 4h18v16H3zM3 10h18M3 15h18M9 4v16M15 4v16",
  "/calidad": "M12 3 2 21h20L12 3zm0 6v5m0 3h.01",
  more: "M5 12h.01M12 12h.01M19 12h.01",
  mic: "M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM6 11a6 6 0 0 0 12 0M12 17v4",
  box: "M4 7l8-4 8 4-8 4-8-4zm0 0v10l8 4 8-4V7M12 11v10",
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
  `flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 px-0.5 text-sm ${
    active ? "text-ink" : "text-muted"
  }`;

/** Bottom tab bar for phones: four main sections plus a "Más" sheet. */
export function MobileNav({
  groups,
  tabs,
  canCreate = false,
  isCorte = false,
}: {
  groups: NavGroup[];
  tabs: NavItem[];
  /** Shows the centered "+" button with the quick actions. */
  canCreate?: boolean;
  isCorte?: boolean;
}) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  // With the center button, the bar is 2 tabs | + | 1 tab + "Más".
  const visibleTabs = canCreate ? tabs.slice(0, 3) : tabs;
  const leftTabs = canCreate ? visibleTabs.slice(0, 2) : visibleTabs;
  const rightTabs = canCreate ? visibleTabs.slice(2) : [];
  const moreActive =
    !visibleTabs.some((item) => isActive(pathname, item.href)) &&
    groups.some((group) =>
      group.items.some((item) => isActive(pathname, item.href)),
    );

  // Close the sheet whenever the route changes.
  // biome-ignore lint/correctness/useExhaustiveDependencies: pathname is the trigger
  useEffect(() => {
    setOpen(false);
    setCreateOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!open && !createOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        setCreateOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, createOpen]);

  const renderTab = (item: NavItem) => {
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
  };

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
            {groups.map((group) => (
              <section
                key={group.title}
                aria-label={group.title}
                className="mb-3 last:mb-0"
              >
                <h2 className="px-4 pb-1 text-xs font-semibold uppercase tracking-caps-sm text-muted">
                  {group.title}
                </h2>
                <ul>
                  {group.items.map((item) => {
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
              </section>
            ))}
          </div>
        </>
      ) : null}
      {createOpen ? (
        <>
          <button
            type="button"
            aria-label="Cerrar acciones"
            onClick={() => setCreateOpen(false)}
            className="fixed inset-0 z-30 bg-ink/40"
          />
          <div
            id="acciones-rapidas"
            className="fixed inset-x-4 bottom-[calc(5.5rem+env(safe-area-inset-bottom))] z-40 rounded-2xl border border-line bg-surface p-2 shadow-card"
          >
            <Link
              href="/corte"
              className="flex min-h-14 items-center gap-3 rounded-card px-4 text-base text-ink"
            >
              <Icon path={ICONS["/corte"]} />
              <span>Cortar</span>
            </Link>
            <Link
              href="/voz"
              className="flex min-h-14 items-center gap-3 rounded-card px-4 text-base text-ink"
            >
              <Icon path={ICONS.mic} />
              <span>Grabar por voz</span>
            </Link>
            {isCorte ? null : (
              <Link
                href="/productos/nuevo"
                className="flex min-h-14 items-center gap-3 rounded-card px-4 text-base text-ink"
              >
                <Icon path={ICONS.box} />
                <span>Nuevo producto</span>
              </Link>
            )}
          </div>
        </>
      ) : null}
      <nav
        aria-label="Secciones"
        className="fixed inset-x-0 bottom-0 z-50 flex border-t border-line bg-surface pb-[env(safe-area-inset-bottom)]"
      >
        {leftTabs.map(renderTab)}
        {canCreate ? (
          <div className="flex flex-1 items-start justify-center">
            <button
              type="button"
              aria-label="Crear"
              aria-expanded={createOpen}
              aria-controls="acciones-rapidas"
              onClick={() => {
                setOpen(false);
                setCreateOpen((value) => !value);
              }}
              className="-mt-5 flex size-14 items-center justify-center rounded-full bg-ink text-white shadow-card"
            >
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                className={`size-7 transition-transform ${createOpen ? "rotate-45" : ""}`}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              >
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          </div>
        ) : null}
        {rightTabs.map(renderTab)}
        {isCorte ? null : (
          <button
            type="button"
            aria-expanded={open}
            aria-controls="mas-secciones"
            onClick={() => {
              setCreateOpen(false);
              setOpen((value) => !value);
            }}
            className={tabClass(open || moreActive)}
          >
            <Icon path={ICONS.more} />
            <span>Más</span>
          </button>
        )}
      </nav>
    </div>
  );
}
