import Link from "next/link";

export type View = "secciones" | "tabla";

export function selectedView(value: string | string[] | undefined): View {
  return (Array.isArray(value) ? value[0] : value) === "tabla"
    ? "tabla"
    : "secciones";
}

export function ViewSelector({
  path,
  params,
  view,
}: {
  path: string;
  params: URLSearchParams;
  view: View;
}) {
  return (
    <nav aria-label="Vista" className="flex flex-wrap gap-2">
      {(["secciones", "tabla"] as const).map((option) => {
        const query = new URLSearchParams(params);
        if (option === "tabla") query.set("vista", "tabla");
        else query.delete("vista");
        const href = query.size ? `${path}?${query}` : path;
        return (
          <Link
            key={option}
            href={href}
            aria-current={view === option ? "page" : undefined}
            className={`inline-flex min-h-11 items-center rounded-card border px-4 py-2 text-sm sm:min-h-0 ${view === option ? "border-ink bg-ink text-white" : "border-line bg-surface hover:border-gold"}`}
          >
            {option === "tabla" ? "Todo junto" : "Por secciones"}
          </Link>
        );
      })}
    </nav>
  );
}
