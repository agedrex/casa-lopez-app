import type { Metadata } from "next";
import { Wordmark } from "@/components/wordmark";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Ingresar" };

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-10 sm:px-8 sm:py-16">
      <div className="w-full max-w-sm">
        <div className="mb-10">
          <Wordmark />
        </div>
        <h1 className="mb-2 text-3xl">Ingresar</h1>
        <p className="mb-8 text-sm text-muted">
          Usá el correo y la contraseña que te dio el administrador.
        </p>
        <LoginForm />
      </div>
    </main>
  );
}
