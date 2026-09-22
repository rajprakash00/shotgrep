import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The web Docker image runs the traced standalone server (docker-compose.yml).
  output: "standalone",
};

export default nextConfig;
