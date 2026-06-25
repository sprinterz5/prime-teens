import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Header } from "@/components/marketing/header";
import { LeadForm } from "@/components/marketing/lead-form";
import { Section } from "@/components/marketing/section";
import { services } from "@/lib/content";

export const metadata: Metadata = {
  title: "Услуги",
  description: "Услуги PrimeTeens: полное сопровождение, консультации, проекты, портфолио и события для подростков."
};

export default function ServicesPage() {
  return (
    <>
      <Header />
      <main>
        <section className="border-b border-white/10 bg-navy-950">
          <div className="mx-auto w-full max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
            <p className="mb-4 text-sm font-semibold text-gold-300">Услуги PrimeTeens</p>
            <h1 className="max-w-4xl font-display text-4xl font-extrabold leading-tight text-porcelain sm:text-6xl">
              Форматы работы будут уточняться, но ядро уже есть: сопровождение подростка и семьи.
            </h1>
            <p className="mt-6 max-w-3xl text-lg leading-8 text-muted">
              Мы не привязываем сайт к одному курсу или гайду. Услуги можно развивать постепенно: от консультаций до полного сопровождения и проектных форматов.
            </p>
          </div>
        </section>

        <Section tone="light" title="Основные направления">
          <div className="grid gap-5">
            {services.map((service) => (
              <article id={service.slug} key={service.slug} className="rounded-lg border border-navy-900/10 bg-white p-6 shadow-sm">
                <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
                  <div>
                    <p className="mb-3 text-sm font-semibold text-gold-500">{service.kicker}</p>
                    <h2 className="font-display text-3xl font-bold text-navy-900">{service.title}</h2>
                    <p className="mt-4 text-base leading-7 text-navy-700">{service.description}</p>
                    <p className="mt-5 text-sm font-semibold text-navy-900">{service.bestFor}</p>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {service.includes.map((item) => (
                      <div key={item} className="flex gap-3 rounded-lg bg-navy-900/[0.04] p-4 text-sm leading-6 text-navy-700">
                        <CheckCircle2 className="mt-0.5 shrink-0 text-gold-500" size={18} aria-hidden="true" />
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              </article>
            ))}
          </div>
        </Section>

        <Section
          id="contact"
          eyebrow="Следующий шаг"
          title="Если услуга пока не названа идеально - это нормально"
          subtitle="Можно начать с описания ситуации. Мы поймем, нужен ли семье полный формат, консультация, проектная работа или что-то другое."
        >
          <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
            <div className="glass rounded-lg p-6">
              <h2 className="font-display text-2xl font-bold">Сайт заложен под рост линейки услуг</h2>
              <p className="mt-4 text-sm leading-6 text-muted">
                Когда появятся точные пакеты, цены, длительность и условия, их можно добавить в этот раздел без переделки всей структуры.
              </p>
              <Link href="/about" className="focus-ring mt-6 inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-gold-300">
                Узнать о PrimeTeens
                <ArrowRight size={16} aria-hidden="true" />
              </Link>
            </div>
            <LeadForm buttonLabel="Отправить заявку" requestType="services" />
          </div>
        </Section>
      </main>
    </>
  );
}
