import type { NextConfig } from "next";
import createMDX from "@next/mdx";

const nextConfig: NextConfig = {
  /* config options here */
  pageExtensions: ['mdx', 'ts', 'tsx'],
  experimental: {
    // React <ViewTransition> support (animated page/language switches).
    viewTransition: true,
  },
  allowedDevOrigins: ['100.118.108.3', 'fm01bot.gamrtag.xyz'],
  images: {
    // Only the placeholder icon the promoted servers use; a wildcard lets anyone make the server fetch and resize
    // endless distinct images.
    remotePatterns: [new URL("https://picsum.photos/1080/1080")],
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Strict-Transport-Security", value: "max-age=31536000" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'; base-uri 'self'; object-src 'none'" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default createMDX({
  extension: /\.mdx$/,
})(nextConfig);
