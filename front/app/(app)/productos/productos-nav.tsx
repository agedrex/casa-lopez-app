"use client";

import { SectionTabs } from "@/components/section-tabs";

const TABS = [
  { href: "/productos", title: "Productos", exact: true },
  { href: "/productos/modelos", title: "Modelos" },
  { href: "/productos/catalogos", title: "Catálogos" },
];

/** Tabs for the admin-only areas of Productos: the list, the models and the colors and categories. */
export function ProductosNav() {
  return <SectionTabs label="Secciones de productos" tabs={TABS} />;
}
