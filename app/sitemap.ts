import type { MetadataRoute } from "next";
import { guides, posts, tracks } from "@/lib/content";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://primeteens.kz";
  const now = new Date();

  return [
    { url: base, lastModified: now },
    { url: `${base}/services`, lastModified: now },
    { url: `${base}/guides`, lastModified: now },
    { url: `${base}/about`, lastModified: now },
    { url: `${base}/blog`, lastModified: now },
    { url: `${base}/privacy`, lastModified: now },
    ...posts.map((post) => ({
      url: `${base}/blog/${post.slug}`,
      lastModified: new Date(post.publishedAt)
    })),
    ...tracks.map((track) => ({
      url: `${base}/blog/tag/${track.slug}`,
      lastModified: now
    })),
    ...guides
      .filter((guide) => guide.status === "available")
      .map((guide) => ({
        url: `${base}${guide.file}`,
        lastModified: now
      }))
  ];
}
