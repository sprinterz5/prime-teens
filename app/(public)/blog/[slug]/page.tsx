import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, CalendarDays, Clock3 } from "lucide-react";
import { Header } from "@/components/marketing/header";
import { getPost, posts, tracks } from "@/lib/content";

type PageProps = {
  params: Promise<{ slug: string }>;
};

export function generateStaticParams() {
  return posts.map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);

  if (!post) {
    return {};
  }

  return {
    title: post.title,
    description: post.excerpt,
    openGraph: {
      title: post.title,
      description: post.excerpt,
      type: "article"
    }
  };
}

export default async function BlogPostPage({ params }: PageProps) {
  const { slug } = await params;
  const post = getPost(slug);

  if (!post) {
    notFound();
  }

  const track = tracks.find((item) => item.slug === post.track);

  return (
    <>
      <Header />
      <main>
        <article className="mx-auto w-full max-w-3xl px-4 py-14 sm:px-6 lg:px-8">
          <Link href="/blog" className="focus-ring mb-8 inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-gold-300">
            <ArrowLeft size={16} aria-hidden="true" />
            Назад в блог
          </Link>

          <div className="mb-6 flex flex-wrap gap-3 text-sm text-muted">
            <span className="rounded-lg border border-gold-400/30 bg-gold-400/10 px-3 py-1 text-gold-300">{post.tag}</span>
            <span className="inline-flex items-center gap-2">
              <Clock3 size={15} aria-hidden="true" />
              {post.readTime}
            </span>
            <span className="inline-flex items-center gap-2">
              <CalendarDays size={15} aria-hidden="true" />
              {new Intl.DateTimeFormat("ru-KZ", { dateStyle: "long" }).format(new Date(post.publishedAt))}
            </span>
          </div>

          <h1 className="font-display text-4xl font-extrabold leading-tight text-porcelain sm:text-5xl">{post.title}</h1>
          <p className="mt-5 text-lg leading-8 text-muted">{post.excerpt}</p>

          <div className="mt-10 space-y-6 text-base leading-8 text-champagne">
            {post.body.map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>

          {track && (
            <aside className="glass mt-12 rounded-lg p-6">
              <p className="text-sm font-semibold text-gold-300">Связанная категория</p>
              <h2 className="mt-2 font-display text-2xl font-bold text-porcelain">{track.title}</h2>
              <p className="mt-3 text-sm leading-6 text-muted">{track.detail}</p>
              <Link href="/#contact" className="focus-ring mt-5 inline-flex rounded-lg text-sm font-semibold text-gold-300">
                Записаться на ассессмент
              </Link>
            </aside>
          )}
        </article>
      </main>
    </>
  );
}
