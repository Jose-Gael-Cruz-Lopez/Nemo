import type { NextConfig } from "next";

const publicShowcase = process.env.TIDEWARD_PUBLIC_SHOWCASE === "true";

const nextConfig: NextConfig = {
  // Emit the minimal production server; runtime does not compile this TS config.
  output: "standalone",
  // The local UI talks to one origin. Operator authorization still belongs to
  // FastAPI, and provider keys are never made available to the Next client.
  experimental: { proxyTimeout: 120_000 },
  rewrites: async () => publicShowcase ? [] : [
    { source: "/api/v1/:path*", destination: "http://127.0.0.1:8000/api/v1/:path*" },
  ],
  // Cloud preview is explicitly read-only; local operator/camera pages stay local.
  redirects: async () => publicShowcase ? ["/", "/workspace", "/login"].map(source => ({ source, destination: "/demo", permanent: false })) : [],
};

export default nextConfig;
