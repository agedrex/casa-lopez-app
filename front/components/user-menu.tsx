"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { authClient } from "@/lib/auth-client";

export function UserMenu({
  name,
  email,
  roleLabel,
}: {
  name: string;
  email: string;
  roleLabel: string;
}) {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function signOut() {
    setPending(true);
    try {
      await authClient.signOut();
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <details className="relative">
      <summary className="flex min-h-11 cursor-pointer list-none items-center gap-3 rounded-card px-2 py-1.5 hover:bg-parchment">
        <span className="hidden text-right leading-tight sm:block">
          <span className="block text-sm">{name}</span>
          <span className="block text-xs text-muted">{roleLabel}</span>
        </span>
        <span
          aria-hidden="true"
          className="grid size-9 place-items-center rounded-full bg-ink font-display text-sm text-white"
        >
          {name.trim().charAt(0).toUpperCase() || "?"}
        </span>
        <span className="sr-only">Menú de usuario</span>
      </summary>
      <div className="absolute right-0 z-10 mt-2 w-[min(16rem,calc(100vw-2rem))] rounded-card border border-line bg-surface p-4 shadow-card">
        <p className="text-sm">{name}</p>
        <p className="truncate text-xs text-muted">{email}</p>
        <p className="mt-1 text-xs uppercase tracking-caps-sm text-gold-deep">
          {roleLabel}
        </p>
        <button
          type="button"
          onClick={signOut}
          disabled={pending}
          className="mt-4 min-h-11 w-full rounded-card border border-ink px-3 py-2 text-sm hover:bg-ink hover:text-white disabled:opacity-60"
        >
          {pending ? "Cerrando sesión…" : "Cerrar sesión"}
        </button>
      </div>
    </details>
  );
}
