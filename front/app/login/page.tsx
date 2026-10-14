import type { Metadata } from "next";
import { Suspense } from "react";
import { LoginForm } from "@/app/login/login-form";

export const metadata: Metadata = { title: "Ingresar | Casa López" };

export default function LoginPage() {
  return (
    <main>
      <section aria-labelledby="login-title">
        <h1 id="login-title">Ingresar</h1>
        <p>Accedé al espacio interno de Casa López.</p>
        <Suspense fallback={<p>Preparando ingreso…</p>}>
          <LoginForm />
        </Suspense>
      </section>
    </main>
  );
}
