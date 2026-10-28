"use client";

import { createAuthClient } from "better-auth/react";

// Same origin as the app: requests go to /api/auth/* on the Next server.
export const authClient = createAuthClient();
