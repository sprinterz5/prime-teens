import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Header } from "@/components/marketing/header";
import { PostCard } from "@/components/blog/post-card";
import { posts, tracks } from "@/lib/content";

type PageProps = {
  params: Promise<{ tag: string }>;
};

export function generateStaticParams() {
  return tracks.map((track) => ({ tag: track.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { tag } = await params;
  const track = tracks.find((item) => item.slug === tag);

  return {
    title: track ? `Категория: ${track.title}` : "Категория"
  };
}

export default async function TagPage({ params }: PageProps) {
  const { tag } = await params;
  const track = tracks.find((item) => item.slug === tag);

  if (!track) {
    notFound();
  }

  const filtered = posts.filter((post) => post.track === track.slug);

  return (
    <>
      <Header />
      <main className="mx-auto w-full max-w-7xl px-4 py-14 sm:px-6 lg:px-8">
        <p className="mb-4 text-sm font-semibold text-gold-300">Категория блога</p>
        <h1 className="font-display text-4xl font-extrabold text-porcelain">{track.title}</h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted">{track.detail}</p>
        <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filtered.length > 0 ? (
            filtered.map((post) => <PostCard key={post.slug} post={post} />)
          ) : (
            <p className="text-muted">Материалы для этой категории появятся скоро.</p>
          )}
        </div>
      </main>
    </>
  );
}
