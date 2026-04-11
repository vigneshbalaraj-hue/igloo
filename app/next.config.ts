import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      // Bare domain → www so Clerk session cookies work
      // (users sign in at app.igloo.video; igloo.video has no Clerk session)
      {
        source: "/:path*",
        has: [{ type: "host", value: "igloo.video" }],
        destination: "https://www.igloo.video/:path*",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
