import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Dev only: lets the Telegram Mini App reach `next dev` through a temporary
  // Cloudflare quick tunnel (HMR and /_next assets are blocked cross-origin
  // otherwise). Has no effect on production builds.
  allowedDevOrigins: ["*.trycloudflare.com"],
  // The floating dev-mode badge overlaps the workbook's top bar in the Mini App.
  devIndicators: false
};

export default nextConfig;
