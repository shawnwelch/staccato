import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Internal ops tool: no image optimization service, no telemetry surprises.
  poweredByHeader: false,
};

export default nextConfig;
