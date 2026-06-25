import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, HeartHandshake, Target, UsersRound } from "lucide-react";
import { Header } from "@/components/marketing/header";
import { Section } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "О нас",
  description: "О PrimeTeens: команда, подход и принципы работы с подростками и родителями."
};

const principles = [
  {
    icon: Target,
    title: "Индивидуальность",
    text: "Мы не делаем вид, что всем нужен один и тот же путь. Подростки разные, семьи разные, цели тоже."
  },
  {
    icon: UsersRound,
    title: "Две аудитории",
    text: "С подростком важно говорить на языке действия, с родителем - на языке стратегии, доверия и сроков."
  },
  {
    icon: HeartHandshake,
    title: "Поддержка без давления",
    text: "Задача не в том, чтобы загрузить подростка, а в том, чтобы помочь ему двигаться осмысленно."
  }
];

export default function AboutPage() {
  return (
    <>
      <Header />
      <main>
        <section className="border-b border-white/10 bg-navy-950">
          <div className="mx-auto grid w-full max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-[1fr_0.7fr] lg:px-8">
            <div>
              <p className="mb-4 text-sm font-semibold text-gold-300">О PrimeTeens</p>
              <h1 className="font-display text-4xl font-extrabold leading-tight text-porcelain sm:text-6xl">
                Мы помогаем подросткам собрать не просто список активностей, а понятную историю о себе.
              </h1>
              <p className="mt-6 max-w-3xl text-lg leading-8 text-muted">
                PrimeTeens работает на стыке подросткового развития, образовательной стратегии, проектов и портфолио. Услуги могут развиваться, но принцип остается один: сначала понять человека, потом строить маршрут.
              </p>
            </div>
            <Image
              src="/prime-teens-logo.png"
              alt="PrimeTeens"
              width={420}
              height={420}
              className="mx-auto aspect-square w-full max-w-sm rounded-lg object-cover"
              priority
            />
          </div>
        </section>

        <Section tone="light" title="Принципы работы">
          <div className="grid gap-4 md:grid-cols-3">
            {principles.map((item) => {
              const Icon = item.icon;
              return (
                <article key={item.title} className="rounded-lg border border-navy-900/10 bg-white p-6 shadow-sm">
                  <Icon className="mb-5 text-gold-500" size={30} aria-hidden="true" />
                  <h2 className="font-display text-xl font-bold">{item.title}</h2>
                  <p className="mt-3 text-sm leading-6 text-navy-700">{item.text}</p>
                </article>
              );
            })}
          </div>
        </Section>

        <Section
          title="Что важно сейчас"
          subtitle="Сайт пока не обязан идеально перечислять все будущие продукты. Важно, чтобы он не сужал PrimeTeens до курсов или гайдов. Поэтому структура уже разделяет компанию, услуги, блог и библиотеку материалов."
        >
          <Link href="/services" className="focus-ring inline-flex items-center gap-2 rounded-lg bg-gold-500 px-5 py-3 font-semibold text-navy-950 transition hover:bg-gold-400">
            Перейти к услугам
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </Section>
      </main>
    </>
  );
}
