import type { NextConfig } from "next";
import { securityHeaders } from "./lib/security-headers";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // Railway keeps the build cache between deploys; with Turbopack's persistent build cache a deploy of staging
    // kept serving a stale compiled stylesheet (body font Lato from an old commit instead of Nunito). A clean
    // compile every time costs a few seconds and makes the build depend only on the commit.
    turbopackFileSystemCacheForBuild: false,
    // Supplier documents go through a server action: files are up to 10 MB each (one per
    // call) plus the form fields. The default is 1 MB. The proxy buffers bodies too (10 MB
    // by default), so it needs the same room. The backend stays the authority on size.
    serverActions: { bodySizeLimit: "12mb" },
    proxyClientMaxBodySize: "12mb",
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: securityHeaders({
          dev: process.env.NODE_ENV !== "production",
        }),
      },
    ];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
