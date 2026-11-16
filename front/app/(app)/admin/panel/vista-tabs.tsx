import Link from "next/link";

/** The views of the merged Panel. Costs come first: it is a costs app, and Negocio explains the same numbers from the money side. */
export const VISTAS_DEL_PANEL = {
  costos: {
    title: "Costos",
    description: "Los costos del mes comparados con el anterior.",
  },
  gastos: {
    title: "Gastos del negocio",
    description:
      "Cuánto gasta el negocio por mes, venda o no venda, repartido entre la fábrica y la tienda.",
  },
  fabrica: {
    title: "Fábrica",
    description:
      "Cuánto tiene que vender la fábrica para cubrir sus costos fijos.",
  },
  tienda: {
    title: "Tienda",
    description:
      "Cuánto tiene que vender la tienda para cubrir sus costos fijos.",
  },
} as const;

export type VistaDelPanel = keyof typeof VISTAS_DEL_PANEL;

/** An unknown or empty ?vista= lands on Costos. */
export function vistaDelPanel(requested: string): VistaDelPanel {
  return (
    (Object.keys(VISTAS_DEL_PANEL) as VistaDelPanel[]).find(
      (id) => id === requested,
    ) ?? "costos"
  );
}

/** Tabs inside the Panel screen; the view lives in the URL (?vista=), Costos being the default without it. */
export function VistaTabs({
  vista,
  periodo,
}: {
  vista: VistaDelPanel;
  periodo: string;
}) {
  return (
    <nav
      aria-label="Vistas del panel"
      className="-mx-4 mb-6 overflow-x-auto overscroll-x-contain border-b border-line px-4 sm:mx-0 sm:mb-8 sm:px-0"
    >
      <ul className="flex min-w-max gap-1">
        {(Object.keys(VISTAS_DEL_PANEL) as VistaDelPanel[]).map((id) => {
          const query = new URLSearchParams();
          if (id !== "costos") query.set("vista", id);
          if (id !== "costos" && periodo) query.set("periodo", periodo);
          const text = query.toString();
          return (
            <li key={id}>
              <Link
                href={text ? `/admin/panel?${text}` : "/admin/panel"}
                aria-current={vista === id ? "page" : undefined}
                className={`-mb-px flex min-h-11 items-center whitespace-nowrap border-b-2 px-3 text-sm transition-colors ${
                  vista === id
                    ? "border-gold text-ink"
                    : "border-transparent text-muted hover:text-ink"
                }`}
              >
                {VISTAS_DEL_PANEL[id].title}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
