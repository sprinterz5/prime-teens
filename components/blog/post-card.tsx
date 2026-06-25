import Link from "next/link";
import { ArrowUpRight, Clock3 } from "lucide-react";
import type { Post } from "@/lib/content";

export function PostCard({ post }: { post: Post }) {
  return (
    <article className="glass flex h-full flex-col rounded-lg p-5">
      <div className="mb-5 flex items-center justify-between gap-3 text-xs text-muted">
        <span className="rounded-lg border border-gold-400/30 bg-gold-400/10 px-3 py-1 text-gold-300">{post.tag}</span>
        <span className="inline-flex items-center gap-1">
          <Clock3 size={14} aria-hidden="true" />
          {post.readTime}
        </span>
      </div>
      <h3 className="font-display text-xl font-bold leading-snug text-porcelain">{post.title}</h3>
      <p className="mt-3 flex-1 text-sm leading-6 text-muted">{post.excerpt}</p>
      <Link href={`/blog/${post.slug}`} className="focus-ring mt-6 inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-gold-300">
        Читать
        <ArrowUpRight size={16} aria-hidden="true" />
      </Link>
    </article>
  );
}
