"use client";

import { useSearchParams } from "next/navigation";
import { type FormEvent, useState } from "react";
import {
  authClient,
  getSafeRedirectPath,
  submitLogin,
} from "@/lib/auth-client";

export function LoginForm() {
  const searchParams = useSearchParams();
  const callbackURL = getSafeRedirectPath(
    searchParams.get("next") ?? undefined,
  );
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    const formData = new FormData(event.currentTarget);
    try {
      const result = await submitLogin(authClient.signIn, {
        email: String(formData.get("email") ?? ""),
        password: String(formData.get("password") ?? ""),
        callbackURL,
      });
      if (!result.ok) {
        setError(
          result.reason === "credentials"
            ? "No se pudo iniciar sesión. Revisá el correo y la contraseña."
            : "No se pudo iniciar sesión. Intentá de nuevo.",
        );
        return;
      }
      window.location.assign(callbackURL);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="email">Correo electrónico</label>
      <input
        autoComplete="username"
        id="email"
        name="email"
        required
        type="email"
      />
      <label htmlFor="password">Contraseña</label>
      <input
        autoComplete="current-password"
        id="password"
        name="password"
        required
        type="password"
      />
      {error ? <p role="alert">{error}</p> : null}
      <button disabled={isSubmitting} type="submit">
        {isSubmitting ? "Ingresando…" : "Ingresar"}
      </button>
    </form>
  );
}
