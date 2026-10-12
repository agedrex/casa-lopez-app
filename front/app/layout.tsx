import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Casa López | Prototipo",
  description:
    "Espacio de descubrimiento para el prototipo de costos de Casa López.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
