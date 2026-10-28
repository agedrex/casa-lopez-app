"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { authClient } from "@/lib/auth-client";
import { safeNext } from "@/lib/redirect";

// One message for unknown user and wrong password: the form never reveals which
// emails exist.
const INVALID_CREDENTIALS = "El correo o la contraseña no son correctos.";
const TOO_MANY_ATTEMPTS =
  "Hubo demasiados intentos. Espere unos instantes y vuelva a probar.";
const UNAVAILABLE =
  "No pudimos iniciar sesión. Intente nuevamente en unos minutos.";

export function LoginForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    if (!email || !password) {
      setError("Ingrese su correo y su contraseña.");
      return;
    }

    setPending(true);
    try {
      const { error: failure } = await authClient.signIn.email({
        email,
        password,
      });
      if (failure) {
        const status = failure.status;
        if (status === 429) setError(TOO_MANY_ATTEMPTS);
        else if (status === 400 || status === 401 || status === 403)
          setError(INVALID_CREDENTIALS);
        else setError(UNAVAILABLE);
        return;
      }
      const next = safeNext(
        new URLSearchParams(window.location.search).get("next"),
      );
      router.replace(next);
      router.refresh();
    } catch {
      setError(UNAVAILABLE);
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-6">
      {error ? (
        <p
          role="alert"
          className="rounded-card border border-bordeaux/30 bg-bordeaux/5 px-4 py-3 text-sm text-bordeaux"
        >
          {error}
        </p>
      ) : null}
      <div>
        <label
          htmlFor="email"
          className="mb-2 block text-xs uppercase tracking-caps-sm text-muted"
        >
          Correo electrónico
        </label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          required
          className="w-full rounded-card border border-line bg-surface px-4 py-3 text-sm outline-none focus:border-gold"
        />
      </div>
      <div>
        <label
          htmlFor="password"
          className="mb-2 block text-xs uppercase tracking-caps-sm text-muted"
        >
          Contraseña
        </label>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className="w-full rounded-card border border-line bg-surface px-4 py-3 text-sm outline-none focus:border-gold"
        />
      </div>
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-card bg-ink px-4 py-3 text-sm uppercase tracking-caps-sm text-white transition-colors hover:bg-ink-soft disabled:opacity-60"
      >
        {pending ? "Ingresando…" : "Ingresar"}
      </button>
    </form>
  );
}
