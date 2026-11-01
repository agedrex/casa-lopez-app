import Link from "next/link";
import type { ReactNode } from "react";
import { linkButtonClass } from "@/components/cueros/estilos";

/** One screen of the cutting flow: a single question, big targets, a way back. */
export function Paso({
  titulo,
  detalle,
  volver,
  children,
}: {
  titulo: string;
  detalle?: string;
  volver?: string;
  children: ReactNode;
}) {
  return (
    <section className="space-y-5">
      <div>
        <h2 className="text-2xl">{titulo}</h2>
        {detalle ? (
          <p className="mt-1 text-base text-muted">{detalle}</p>
        ) : null}
      </div>
      {children}
      {volver ? (
        <Link href={volver} className={linkButtonClass}>
          Volver
        </Link>
      ) : null}
    </section>
  );
}
