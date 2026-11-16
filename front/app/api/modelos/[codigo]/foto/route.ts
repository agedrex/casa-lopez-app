import { apiGetFile } from "@/lib/api";
import { parseRoles } from "@/lib/permissions";
import { getSession } from "@/lib/session";

const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

/**
 * Streams the current photo of a model to the browser with the visitor's session, so an `<img src>` works with the
 * session cookie. The browser only knows this same-origin path; the backend address never leaves the server. Every role
 * with a recognized role reads it (the backend checks the role again), and only an image type is passed on.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ codigo: string }> },
) {
  const session = await getSession();
  if (!session) return new Response("No autorizado", { status: 401 });
  if (parseRoles(session.user.role).length === 0) {
    return new Response("Sin permiso", { status: 403 });
  }

  const { codigo } = await params;
  if (!/^[A-Za-z0-9-]{1,40}$/.test(codigo)) {
    return new Response("No encontrado", { status: 404 });
  }

  const result = await apiGetFile(`/modelos/${codigo}/foto`);
  if (!result.ok) {
    return new Response(result.message, {
      status: result.status === 404 ? 404 : result.status === 403 ? 403 : 502,
    });
  }

  const type = result.response.headers.get("content-type");
  if (!type || !IMAGE_TYPES.includes(type)) {
    return new Response("Tipo de archivo no válido", { status: 502 });
  }
  const headers = new Headers({
    "Content-Type": type,
    // Short: a new upload must show up soon (the backend uses the same value).
    "Cache-Control": "private, max-age=60",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
  });
  const length = result.response.headers.get("content-length");
  if (length) headers.set("Content-Length", length);
  return new Response(result.response.body, { status: 200, headers });
}
