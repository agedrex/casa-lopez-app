import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  experimental: {
    // Supplier documents go through a server action: files are up to 10 MB each (one per
    // call) plus the form fields. The default is 1 MB. The proxy buffers bodies too (10 MB
    // by default), so it needs the same room. The backend stays the authority on size.
    serverActions: { bodySizeLimit: "12mb" },
    proxyClientMaxBodySize: "12mb",
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
