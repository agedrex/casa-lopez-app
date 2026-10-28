import Link from "next/link";

export function BackToAdmin() {
  return (
    <p className="mb-6 text-sm">
      <Link
        href="/admin"
        className="text-muted underline decoration-gold underline-offset-4"
      >
        ← Administración
      </Link>
    </p>
  );
}
