"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import type { NavGroup, NavItem } from "@/lib/nav";
import { activeSidebarHref } from "./main-nav";
import { ICONS, Icon } from "./nav-icons";

const tabClass = (active: boolean) =>
  `flex min-h-14 flex-1 flex-col items-center justify-center gap-0.5 px-0.5 text-sm ${
    active ? "text-ink" : "text-muted"
  }`;

/** Bottom tab bar for phones: four main sections plus a "Más" sheet. */
export function MobileNav({
  groups,
  tabs,
  canCreate = false,
  restricted = false,
}: {
  groups: NavGroup[];
  tabs: NavItem[];
  /** Shows the centered "+" button with the quick actions. */
  canCreate?: boolean;
  /** Non-admin roles: no "Más" sheet and no quick action that creates products. */
  restricted?: boolean;
}) {
  const pathname = usePathname();
  const search = useSearchParams();
  const [open, setOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  // With the center button, the bar is 2 tabs | + | 1 tab + "Más" (with only 2 tabs: 1 | + | 1).
  // The taller has Voz as a tab, so its "+" would only repeat it: no "+" then.
  const quickActions =
    canCreate && !(restricted && tabs.some((item) => item.href === "/voz"));
  const visibleTabs = quickActions ? tabs.slice(0, 3) : tabs;
  const leftTabs = quickActions
    ? visibleTabs.slice(0, Math.ceil(visibleTabs.length / 2))
    : visibleTabs;
  const rightTabs = quickActions
    ? visibleTabs.slice(Math.ceil(visibleTabs.length / 2))
    : [];
  const visibleItems = groups.flatMap((group) => group.items);
  // Same rule as the desktop sidebar, so the filters (Mano de obra, Servicios básicos) highlight the right entry.
  const activeHref = activeSidebarHref(groups, pathname, search);
  const active = (href: string) => href === activeHref;
  const moreActive =
    !visibleTabs.some((item) => active(item.href)) &&
    visibleItems.some((item) => active(item.href));

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
    const current = active(item.href);
    return (
      <Link
        key={item.href}
        href={item.href}
        aria-current={current ? "page" : undefined}
        className={tabClass(current)}
      >
        <Icon path={ICONS[item.icon ?? item.href] ?? ICONS.more} />
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
            {groups.map((group, index) => (
              <section
                key={`${group.title}-${index}`}
                aria-label={group.title || undefined}
                className="mb-3 last:mb-0"
              >
                {group.title ? (
                  <h2 className="px-4 pb-1 text-xs font-semibold uppercase tracking-caps-sm text-muted">
                    {group.title}
                  </h2>
                ) : null}
                <ul>
                  {group.items.map((item) => {
                    const current = active(item.href);
                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          aria-current={current ? "page" : undefined}
                          className={`flex min-h-12 items-center gap-3 rounded-card px-4 text-base ${
                            current ? "bg-ink text-white" : "text-ink-soft"
                          }`}
                        >
                          <Icon
                            path={ICONS[item.icon ?? item.href] ?? ICONS.more}
                            className="size-5 shrink-0"
                          />
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
      {quickActions && createOpen ? (
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
            {/* Corte is closed to the restricted roles (the taller enters through Lotes). */}
            {restricted ? null : (
              <Link
                href="/corte"
                className="flex min-h-14 items-center gap-3 rounded-card px-4 text-base text-ink"
              >
                <Icon path={ICONS["/corte"]} />
                <span>Cortar</span>
              </Link>
            )}
            <Link
              href="/voz"
              className="flex min-h-14 items-center gap-3 rounded-card px-4 text-base text-ink"
            >
              <Icon path={ICONS.mic} />
              <span>Grabar por voz</span>
            </Link>
            {restricted ? null : (
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
        {quickActions ? (
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
        {restricted ? null : (
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
