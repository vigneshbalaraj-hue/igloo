import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      // Consolidate all domains to igloo.video (the one canonical address)
      {
        source: "/:path*",
        has: [{ type: "host", value: "www.igloo.video" }],
        destination: "https://igloo.video/:path*",
        permanent: true,
      },
      {
        source: "/:path*",
        has: [{ type: "host", value: "app.igloo.video" }],
        destination: "https://igloo.video/:path*",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
