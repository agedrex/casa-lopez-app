import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-md p-8">
      <h1 className="text-lg font-semibold">No encontramos esa página</h1>
      <p className="mt-2 text-sm text-muted">
        El enlace no existe.{" "}
        <Link href="/" className="underline decoration-gold underline-offset-4">
          Volver al inicio
        </Link>
      </p>
    </main>
  );
}
