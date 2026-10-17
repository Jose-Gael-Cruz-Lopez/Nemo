import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The local UI talks to one origin. Operator authorization still belongs to
  // FastAPI, and provider keys are never made available to the Next client.
  experimental: { proxyTimeout: 120_000 },
  rewrites: async () => [
    { source: "/api/v1/:path*", destination: "http://127.0.0.1:8000/api/v1/:path*" },
  ],
};

export default nextConfig;
