import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Download, Lock } from "lucide-react";
import { Footer } from "@/components/marketing/footer";
import { Header } from "@/components/marketing/header";
import { Section } from "@/components/marketing/section";
import { guides } from "@/lib/content";

export const metadata: Metadata = {
  title: "Ресурсы",
  description: "Гайды серии «Сильное портфолио» от PrimeTeens — бесплатные PDF по проектам, волонтёрству, выступлениям и исследованиям."
};

export default function GuidesPage() {
  return (
    <>
      <Header />
      <main>
        <section className="border-b border-white/10 bg-navy-950">
          <div className="mx-auto w-full max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <p className="eyebrow mb-4">Ресурсы</p>
            <h1 className="max-w-4xl font-display text-4xl font-bold leading-tight text-porcelain sm:text-6xl">
              Серия «Сильное портфолио» — бесплатно, без формы, сразу PDF.
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-8 text-muted">
              Гайды помогают быстро разобраться в теме. Для реальной стратегии поступления нужна профориентация и контекст конкретного студента.
            </p>
          </div>
        </section>

        <Section title="Доступные материалы">
          <div className="grid gap-4 md:grid-cols-2">
            {guides.map((guide) =>
              guide.status === "available" ? (
                <a
                  key={guide.slug}
                  href={guide.file}
                  download
                  className="glass card-hover focus-ring group rounded-lg p-6"
                >
                  <span className="eyebrow mb-3">Гайд №{guide.number}</span>
                  <p className="mb-2 text-sm font-semibold text-gold-300">{guide.topic}</p>
                  <h2 className="font-display text-xl font-semibold text-porcelain">{guide.title}</h2>
                  <p className="mt-3 text-sm leading-6 text-muted">{guide.description}</p>
                  <p className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-champagne group-hover:text-gold-300">
                    <Download size={16} aria-hidden="true" />
                    Скачать PDF
                  </p>
                </a>
              ) : (
                <article key={guide.slug} className="glass rounded-lg p-6 opacity-70">
                  <span className="icon-badge mb-5">
                    <Lock size={20} aria-hidden="true" />
                  </span>
                  <p className="mb-2 text-sm font-semibold text-gold-300">{guide.topic}</p>
                  <h2 className="font-display text-xl font-semibold">{guide.title}</h2>
                  <p className="mt-3 text-sm leading-6 text-muted">{guide.description}</p>
                  <p className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-muted">
                    <Lock size={16} aria-hidden="true" />
                    Скоро
                  </p>
                </article>
              )
            )}
          </div>
        </Section>

        <Section
          id="contact"
          tone="light"
          eyebrow="Следующий шаг"
          title="Гайды дают общую картину. Профориентация — конкретный план для вашего студента"
          subtitle="Тест и разбор профиля превращают общие советы в реалистичный список направлений и вузов."
        >
          <Link href="/#contact" className="btn btn-primary focus-ring">
            Записаться на профориентацию
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </Section>
        <Footer />
      </main>
    </>
  );
}
