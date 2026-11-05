import { apiGetFile } from "@/lib/api";
import { canWrite } from "@/lib/permissions";
import { getSession } from "@/lib/session";

/**
 * Streams a supplier document to the browser with the visitor's session. The browser only
 * knows this same-origin path: the backend address never leaves the server. The proxy
 * already keeps non-admins out of /proveedores; the role is checked again here and the
 * backend checks it a third time.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await getSession();
  if (!session) return new Response("No autorizado", { status: 401 });
  if (!canWrite(session.user.role)) {
    return new Response("Sin permiso", { status: 403 });
  }

  const { id } = await params;
  if (!/^\d+$/.test(id)) return new Response("No encontrado", { status: 404 });

  const result = await apiGetFile(`/documentos-proveedor/${id}/archivo`);
  if (!result.ok) {
    return new Response(result.message, {
      status: result.status === 404 ? 404 : 502,
    });
  }

  // Only the headers that describe the file are passed on; the API decides inline/attachment.
  const headers = new Headers({
    "Cache-Control": "private, no-store",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'",
  });
  for (const name of [
    "content-type",
    "content-disposition",
    "content-length",
  ]) {
    const value = result.response.headers.get(name);
    if (value) headers.set(name, value);
  }
  return new Response(result.response.body, { status: 200, headers });
}
