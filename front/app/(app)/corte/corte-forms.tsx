"use client";

import Link from "next/link";
import { linkButtonClass } from "@/components/cueros/estilos";
import {
  FormFeedback,
  PrimaryButton,
  SecondaryButton,
} from "@/components/form";
import { useActionForm } from "@/lib/use-action-form";
import { confirmarCorte, decidirSobrante } from "./actions";

export function ConfirmarCorteForm({
  pieza,
  item,
  lote,
  producto,
  m2,
}: {
  pieza: string;
  item: string;
  lote: string;
  producto: string;
  m2: string;
}) {
  const { state, pending, onSubmit } = useActionForm(confirmarCorte);
  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <input type="hidden" name="pieza" value={pieza} />
      <input type="hidden" name="item" value={item} />
      <input type="hidden" name="lote" value={lote} />
      <input type="hidden" name="producto" value={producto} />
      <input type="hidden" name="m2" value={m2} />
      <FormFeedback state={state} />
      <PrimaryButton pending={pending}>
        {pending ? "Guardando…" : "Confirmar corte"}
      </PrimaryButton>
    </form>
  );
}

export function SobranteForm({
  pieza,
  lote,
  seguirHref,
}: {
  pieza: string;
  lote: string;
  seguirHref: string;
}) {
  const { state, pending, onSubmit } = useActionForm(decidirSobrante);
  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <input type="hidden" name="pieza" value={pieza} />
      <input type="hidden" name="lote" value={lote} />
      <FormFeedback state={state} />
      <div className="flex flex-col gap-3">
        <PrimaryButton pending={pending} name="decision" value="REUTILIZABLE">
          Sí, lo guardo
        </PrimaryButton>
        <SecondaryButton
          pending={pending}
          name="decision"
          value="IRRECUPERABLE"
        >
          No, se descarta
        </SecondaryButton>
        <Link href={seguirHref} className={linkButtonClass}>
          La sigo usando
        </Link>
      </div>
    </form>
  );
}
