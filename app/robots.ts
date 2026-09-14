import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/dashboard",
        "/parent",
        "/student",
        "/curator",
        "/admin",
        "/workbook",
        "/mentor",
        "/dev",
        "/api"
      ]
    },
    sitemap: "https://primeteens.kz/sitemap.xml"
  };
}
