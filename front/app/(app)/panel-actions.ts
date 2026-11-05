"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { PRECIO_COOKIE, precioValido } from "@/lib/precio-panel";

const UN_ANIO = 60 * 60 * 24 * 365;

/** Remembers the typed price (a view preference, nothing is stored in the business data) and reloads the panel. */
export async function guardarPrecio(formData: FormData): Promise<void> {
  const raw = String(formData.get("precio") ?? "").trim();
  const jar = await cookies();
  if (!raw) {
    jar.delete(PRECIO_COOKIE);
    redirect("/");
  }
  const precio = precioValido(raw);
  if (precio === null) {
    redirect(`/?precio_invalido=${encodeURIComponent(raw)}`);
  }
  jar.set(PRECIO_COOKIE, precio, {
    maxAge: UN_ANIO,
    path: "/",
    sameSite: "lax",
  });
  redirect("/");
}
