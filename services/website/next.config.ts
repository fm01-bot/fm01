import type { NextConfig } from "next";
import createMDX from "@next/mdx";
import path from "path";

// The repo root: the site imports text from ../../shared, which Turbopack only resolves
// inside its root. Docker keeps the same layout (/app/services/website + /app/shared).
const repoRoot = path.join(__dirname, "../..");

const nextConfig: NextConfig = {
  turbopack: { root: repoRoot },
  outputFileTracingRoot: repoRoot,
  pageExtensions: ['mdx', 'ts', 'tsx'],
  experimental: {
    // React <ViewTransition> support (animated page/language switches).
    viewTransition: true,
  },
  allowedDevOrigins: ['100.118.108.3', 'fm01bot.gamrtag.xyz', 'placehold.co'],
  images: {
    remotePatterns: [new URL("https://placehold.co/**"), new URL("https://picsum.photos/**")],

  }
};

export default createMDX({
  extension: /\.mdx$/,
})(nextConfig);
