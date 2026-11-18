import Link from "next/link";
import { PageHeader } from "@/components/ui";

export default function NotFound() {
  return (
    <>
      <PageHeader eyebrow="Error 404" title="No encontramos esa página" />
      <p className="text-sm text-muted">
        El enlace no existe.{" "}
        <Link href="/" className="underline decoration-gold underline-offset-4">
          Volver al inicio
        </Link>
      </p>
    </>
  );
}
