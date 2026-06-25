import type { Metadata } from "next";
import Link from "next/link";
import { Header } from "@/components/marketing/header";
import { PostCard } from "@/components/blog/post-card";
import { posts, tracks } from "@/lib/content";

export const metadata: Metadata = {
  title: "Блог",
  description: "Гайды PrimeTeens по олимпиадам, школьным клубам, хакатонам и портфолио."
};

export default function BlogPage() {
  return (
    <>
      <Header />
      <main>
        <section className="border-b border-white/10 bg-navy-950">
          <div className="mx-auto w-full max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <p className="mb-4 text-sm font-semibold text-gold-300">Блог PrimeTeens</p>
            <h1 className="font-display text-4xl font-extrabold leading-tight text-porcelain sm:text-5xl">
              Гайды и маршруты для сильного портфолио
            </h1>
            <p className="mt-5 max-w-3xl text-base leading-7 text-muted">
              Стартовая лента собрана из готовых материалов PrimeTeens. Категории совпадают с треками портфолио, чтобы блог работал вместе с продуктом.
            </p>
            <div className="mt-8 flex flex-wrap gap-2">
              {tracks.map((track) => (
                <Link
                  key={track.slug}
                  href={`/blog/tag/${track.slug}`}
                  className="focus-ring rounded-lg border border-white/12 px-3 py-2 text-sm text-muted transition hover:border-gold-400/70 hover:text-gold-300"
                >
                  {track.title}
                </Link>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto grid w-full max-w-7xl gap-4 px-4 py-14 sm:px-6 md:grid-cols-2 lg:grid-cols-3 lg:px-8">
          {posts.map((post) => (
            <PostCard key={post.slug} post={post} />
          ))}
        </section>
      </main>
    </>
  );
}
