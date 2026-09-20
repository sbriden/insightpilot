import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  transpilePackages: [
    "@react-pdf/renderer",
  ],
  // Parent dirs also have lockfiles; keep Turbopack rooted here.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
