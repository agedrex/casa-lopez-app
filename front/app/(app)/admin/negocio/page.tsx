import { redirect } from "next/navigation";

type Search = Promise<{
  vista?: string | string[];
  periodo?: string | string[];
}>;

function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

// Negocio was merged into the Panel: its views are now tabs of /admin/panel (the old default, gastos, is kept).
export default async function NegocioPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const params = await searchParams;
  const vista = first(params.vista) || "gastos";
  const query = new URLSearchParams({ vista });
  const periodo = first(params.periodo);
  if (periodo) query.set("periodo", periodo);
  redirect(`/admin/panel?${query}`);
}
