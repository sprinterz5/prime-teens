import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { ArrowRight, HeartHandshake, Target, UsersRound } from "lucide-react";
import { Header } from "@/components/marketing/header";
import { Section } from "@/components/marketing/section";

export const metadata: Metadata = {
  title: "О нас",
  description: "О PrimeTeens: команда, подход и принципы сопровождения поступления."
};

const principles = [
  {
    icon: Target,
    title: "Индивидуальная стратегия",
    text: "Мы не делаем вид, что всем подходит один и тот же список вузов. Профиль, бюджет и цели у каждого студента разные."
  },
  {
    icon: UsersRound,
    title: "Две аудитории",
    text: "Со студентом важно говорить на языке действия и сроков, с родителем - на языке стратегии, прозрачности и договора."
  },
  {
    icon: HeartHandshake,
    title: "Сопровождение, а не давление",
    text: "Задача куратора не в том, чтобы подгонять студента, а в том, чтобы держать процесс собранным и без сорванных дедлайнов."
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
                Мы сопровождаем поступление так, чтобы семья видела прогресс, а не гадала, что происходит.
              </h1>
              <p className="mt-6 max-w-3xl text-lg leading-8 text-muted">
                PrimeTeens работает на стыке профориентации, образовательной стратегии и координации подачи документов. Линейка услуг может расти, но принцип один: сначала понять студента, потом строить маршрут.
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
          subtitle="Сайт растёт вместе с линейкой услуг. Компания, услуги, блог и библиотека материалов уже разделены, чтобы новые пакеты и кабинеты добавлялись без переделки структуры."
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
