import type { Metadata } from "next";
import {
  Card,
  ErrorNotice,
  Notice,
  PageHeader,
  SectionTitle,
  TableWrap,
  tableClass,
  tdClass,
  thClass,
} from "@/components/ui";
import { apiGet } from "@/lib/api";
import { requireRole } from "@/lib/session";
import type { ItemCatalogo } from "@/lib/types";
import { BackToAdmin } from "../back-link";
import { CatalogoForm } from "./catalogo-form";

export const metadata: Metadata = { title: "Catálogos" };

export default async function CatalogosPage() {
  await requireRole("admin");
  const [colores, categorias] = await Promise.all([
    apiGet<ItemCatalogo[]>("/colores"),
    apiGet<ItemCatalogo[]>("/categorias"),
  ]);

  return (
    <>
      <BackToAdmin />
      <PageHeader
        eyebrow="Administración"
        title="Catálogos"
        description="Las listas que se eligen al cargar productos y modelos. El código lo asigna la aplicación y nunca cambia. Nada se borra."
      />
      <div className="grid gap-12 lg:grid-cols-2">
        <Section
          title="Colores"
          noun="color"
          kind="color"
          items={colores}
          empty="Todavía no hay colores: sin ellos, el producto se carga sin color."
        />
        <Section
          title="Categorías"
          noun="categoría"
          kind="categoria"
          items={categorias}
          empty="Todavía no hay categorías."
        />
      </div>
      <div className="mt-10">
        <Notice tone="info" title="Sin desactivar ni borrar">
          Los colores y las categorías todavía no se pueden ocultar: la base no
          tiene una marca de &quot;activo&quot; para ellos. Si hace falta, es un
          cambio de base que se pide aparte.
        </Notice>
      </div>
    </>
  );
}

function Section({
  title,
  noun,
  kind,
  items,
  empty,
}: {
  title: string;
  noun: string;
  kind: "color" | "categoria";
  items: Awaited<ReturnType<typeof apiGet<ItemCatalogo[]>>>;
  empty: string;
}) {
  return (
    <section aria-label={title} className="space-y-6">
      <SectionTitle>{title}</SectionTitle>
      {items.ok ? (
        items.data.length === 0 ? (
          <Notice tone="info" title={empty} />
        ) : (
          <TableWrap>
            <table className={tableClass}>
              <thead>
                <tr>
                  <th className={thClass}>Nombre</th>
                  <th className={thClass}>Código</th>
                </tr>
              </thead>
              <tbody>
                {items.data.map((item) => (
                  <tr key={item.codigo} className="hover:bg-paper-mid/50">
                    <td className={tdClass}>
                      {item.nombre}
                      {item.nota ? (
                        <span className="block text-xs text-muted">
                          {item.nota}
                        </span>
                      ) : null}
                    </td>
                    <td className={tdClass}>{item.codigo}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )
      ) : (
        <ErrorNotice message={items.message} />
      )}
      <Card>
        <CatalogoForm kind={kind} noun={noun} />
      </Card>
    </section>
  );
}
