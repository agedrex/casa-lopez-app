import type { Metadata } from "next";
import { Notice, PageHeader } from "@/components/ui";

export const metadata: Metadata = { title: "Sin acceso" };

export default function SinAccesoPage() {
  return (
    <>
      <PageHeader title="Sin acceso" />
      <Notice tone="info" title="Su usuario no tiene un rol asignado">
        Pídale a un administrador que le asigne un rol para poder ver los datos.
      </Notice>
    </>
  );
}
