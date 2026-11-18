import type { Metadata } from "next";
import { ReadOnlyNote } from "@/components/form";
import { ErrorNotice, PageHeader, SectionTitle } from "@/components/ui";
import { apiGet } from "@/lib/api";
import { canUseVoice } from "@/lib/permissions";
import { requireSession } from "@/lib/session";
import type { VozEstado } from "@/lib/types";
import { VOZ_MAX_CHARS } from "@/lib/voz";
import { ExampleList } from "./examples";
import { VozPanel } from "./voz-panel";

export const metadata: Metadata = { title: "Voz" };

type Search = Promise<{ texto?: string | string[] }>;

export default async function VozPage({
  searchParams,
}: {
  searchParams: Search;
}) {
  const { user } = await requireSession();
  // The header microphone hands over what it heard; the person still reviews it and presses Interpretar.
  const { texto } = await searchParams;
  const dictated = (Array.isArray(texto) ? texto[0] : texto)
    ?.trim()
    .slice(0, VOZ_MAX_CHARS);
  const writer = canUseVoice(user.role);
  const estado = writer ? await apiGet<VozEstado>("/voz/estado") : null;

  return (
    <>
      <PageHeader
        eyebrow="Carga"
        title="Voz"
        description="Escribí un pedido y revisá la propuesta antes de confirmar."
      />
      <div className="space-y-10">
        {writer ? (
          estado?.ok ? (
            <VozPanel
              key={dictated ?? ""}
              configured={estado.data.configurado}
              initialText={dictated}
            />
          ) : (
            <ErrorNotice
              message={estado?.ok === false ? estado.message : "Sin datos."}
            />
          )
        ) : (
          <section>
            <ReadOnlyNote />
            <div className="mt-6">
              <SectionTitle>Ejemplos de pedidos</SectionTitle>
              <ExampleList />
            </div>
          </section>
        )}

        <p className="text-xs text-muted">
          El audio queda en tu teléfono. El texto se envía a Anthropic para
          interpretarlo.
        </p>
      </div>
    </>
  );
}
