import type { Metadata } from "next";
import { Wordmark } from "@/components/wordmark";
import { LoginForm } from "./login-form";

export const metadata: Metadata = { title: "Ingresar" };

export default function LoginPage() {
  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <section className="flex flex-col justify-between bg-ink px-8 py-10 text-white sm:px-14 sm:py-14">
        <Wordmark tone="light" />
        <div className="py-16">
          <p className="mb-5 text-xs uppercase tracking-caps-lg text-gold">
            Marroquinería de Buenos Aires · Desde 1939
          </p>
          <h1 className="font-display text-5xl leading-[1.05] sm:text-6xl">
            El oficio
            <br />
            llevado a la perfección
          </h1>
          <p className="mt-6 max-w-md text-sm text-white/75">
            Costos, materiales y cotizaciones de cada pieza, en un solo lugar.
          </p>
        </div>
        <p className="text-xs text-white/45">Herramienta interna de costos</p>
      </section>
      <section className="flex items-center justify-center px-8 py-16">
        <div className="w-full max-w-sm">
          <h2 className="mb-2 text-3xl">Ingresar</h2>
          <p className="mb-8 text-sm text-muted">
            Use el correo y la contraseña que le dio el administrador.
          </p>
          <LoginForm />
        </div>
      </section>
    </main>
  );
}
