import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  allowedDevOrigins: ['100.118.108.3', 'fm01bot.gamrtag.xyz', 'placehold.co'],
  images: {
    remotePatterns: [new URL("https://placehold.co/**"), new URL("https://picsum.photos/**")],

  }
};

export default nextConfig;
