import { isIP } from "node:net";

export type AdminStatus = {
  authenticated: true;
  user_id: string;
  role: "admin";
};

type FetchLike = (input: URL, init: RequestInit) => Promise<Response>;

type FetchAdminStatusOptions = {
  backendUrl: string | undefined;
  cookie: string | null;
  expectedUserId: string | undefined;
  fetchImpl?: FetchLike;
  timeoutMs?: number;
};

function getStatusUrl(backendUrl: string | undefined) {
  if (!backendUrl) return null;

  try {
    const base = new URL(backendUrl);
    if (
      (base.protocol !== "http:" && base.protocol !== "https:") ||
      base.username ||
      base.password ||
      base.search ||
      base.hash
    ) {
      return null;
    }
    if (base.protocol === "http:" && !isPrivateServiceHost(base.hostname)) {
      return null;
    }

    return new URL("/api/admin/status", base.origin);
  } catch {
    return null;
  }
}

function isPrivateServiceHost(hostname: string) {
  const host = hostname.toLowerCase().replace(/^\[|\]$/g, "");
  if (
    host === "localhost" ||
    host.endsWith(".localhost") ||
    host === "internal" ||
    host.endsWith(".internal")
  ) {
    return true;
  }

  const ipVersion = isIP(host);
  if (ipVersion === 4) {
    const octets = host.split(".").map(Number);
    const [first, second] = octets;
    return (
      first === 10 ||
      first === 127 ||
      (first === 172 && second >= 16 && second <= 31) ||
      (first === 192 && second === 168) ||
      (first === 169 && second === 254)
    );
  }
  if (ipVersion === 6) {
    return host === "::1" || /^(fc|fd|fe[89ab])/i.test(host);
  }
  return false;
}

function parseAdminStatus(
  value: unknown,
  expectedUserId: string,
): AdminStatus | null {
  if (!value || typeof value !== "object") return null;
  const result = value as Record<string, unknown>;
  if (
    result.authenticated !== true ||
    typeof result.user_id !== "string" ||
    result.user_id !== expectedUserId ||
    result.role !== "admin"
  ) {
    return null;
  }

  return {
    authenticated: true,
    user_id: result.user_id,
    role: "admin",
  };
}

export async function fetchAdminStatus({
  backendUrl,
  cookie,
  expectedUserId,
  fetchImpl = fetch as FetchLike,
  timeoutMs = 2_000,
}: FetchAdminStatusOptions): Promise<AdminStatus | null> {
  const url = getStatusUrl(backendUrl);
  if (!url || !cookie || !expectedUserId) return null;

  try {
    const response = await fetchImpl(url, {
      method: "GET",
      headers: { cookie },
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (response.status !== 200) return null;
    return parseAdminStatus(await response.json(), expectedUserId);
  } catch {
    return null;
  }
}
