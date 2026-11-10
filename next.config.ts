import type { NextConfig } from "next";
import createMDX from "@next/mdx";

const nextConfig: NextConfig = {
  /* config options here */
  pageExtensions: ['mdx', 'ts', 'tsx'],
  allowedDevOrigins: ['100.118.108.3', 'fm01bot.gamrtag.xyz', 'placehold.co'],
  images: {
    remotePatterns: [new URL("https://placehold.co/**"), new URL("https://picsum.photos/**")],

  }
};

export default createMDX({
  extension: /\.mdx$/,
})(nextConfig);
