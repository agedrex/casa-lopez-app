import { redirect } from "next/navigation";

// Models moved to Productos; this keeps old links working.
export default async function ModeloMovedPage({
  params,
}: {
  params: Promise<{ codigo: string }>;
}) {
  const { codigo } = await params;
  redirect(`/productos/modelos/${codigo}`);
}
