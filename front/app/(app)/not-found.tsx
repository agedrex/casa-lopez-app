import Link from "next/link";
import { PageHeader } from "@/components/ui";

export default function NotFound() {
  return (
    <>
      <PageHeader eyebrow="Error 404" title="No encontramos esa página" />
      <p className="text-sm text-muted">
        Puede que el producto no exista o que el enlace sea incorrecto.{" "}
        <Link
          href="/productos"
          className="underline decoration-gold underline-offset-4"
        >
          Volver a productos
        </Link>
      </p>
    </>
  );
}
