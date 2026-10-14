import { getAuth } from "@/lib/auth";
import { createInternalSessionHandler } from "@/lib/auth-session";

const handle = createInternalSessionHandler({
  secret: () => process.env.AUTH_INTERNAL_SECRET,
  getSession: (headers) => getAuth().api.getSession({ headers }),
});

export const POST = handle;
