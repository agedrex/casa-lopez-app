"use client";

import { SectionTabs } from "@/components/section-tabs";

const TABS = [
  { href: "/productos", title: "Productos", exact: true },
  { href: "/productos/modelos", title: "Modelos" },
];

/** Tabs for the admin-only areas of Productos: the list and the models. */
export function ProductosNav() {
  return <SectionTabs label="Secciones de productos" tabs={TABS} />;
}
