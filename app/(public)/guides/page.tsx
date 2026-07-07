import type { Metadata } from "next";
import { BookOpen, Download, Lock } from "lucide-react";
import { Header } from "@/components/marketing/header";
import { LeadForm } from "@/components/marketing/lead-form";
import { Section } from "@/components/marketing/section";
import { guides } from "@/lib/content";

export const metadata: Metadata = {
  title: "Ресурсы",
  description: "Гайды и чек-листы PrimeTeens по документам, профориентации и подготовке к экзаменам."
};

export default function GuidesPage() {
  return (
    <>
      <Header />
      <main>
        <section className="border-b border-white/10 bg-navy-950">
          <div className="mx-auto w-full max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <p className="mb-4 text-sm font-semibold text-gold-300">Ресурсы</p>
            <h1 className="max-w-4xl font-display text-4xl font-extrabold leading-tight text-porcelain sm:text-6xl">
              Отдельная библиотека материалов, а не главный продукт PrimeTeens.
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-8 text-muted">
              Гайды помогают быстро разобраться в теме. Для реальной стратегии поступления нужен ассессмент и контекст конкретного студента.
            </p>
          </div>
        </section>

        <Section title="Доступные и будущие материалы">
          <div className="grid gap-4 md:grid-cols-2">
            {guides.map((guide) => (
              <article key={guide.slug} className="glass rounded-lg p-6">
                {guide.status === "available" ? (
                  <BookOpen className="mb-5 text-gold-300" size={30} aria-hidden="true" />
                ) : (
                  <Lock className="mb-5 text-muted" size={30} aria-hidden="true" />
                )}
                <p className="mb-3 text-sm font-semibold text-gold-300">{guide.topic}</p>
                <h2 className="font-display text-2xl font-bold">{guide.title}</h2>
                <p className="mt-3 text-sm leading-6 text-muted">{guide.description}</p>
                <p className="mt-5 inline-flex items-center gap-2 text-sm font-semibold text-champagne">
                  {guide.status === "available" ? <Download size={16} aria-hidden="true" /> : <Lock size={16} aria-hidden="true" />}
                  {guide.status === "available" ? "Можно запросить" : "Скоро"}
                </p>
              </article>
            ))}
          </div>
        </Section>

        <Section
          id="contact"
          tone="light"
          eyebrow="Получить материал"
          title="Оставьте email, если нужен один из гайдов"
          subtitle="Позже здесь можно сделать нормальную библиотеку с отдельными страницами и PDF-файлами. Сейчас форма фиксирует интерес к материалам."
        >
          <LeadForm buttonLabel="Запросить гайд" interest="guide" />
        </Section>
      </main>
    </>
  );
}
