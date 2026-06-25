import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  CalendarCheck,
  CheckCircle2,
  ClipboardList,
  Compass,
  FileText,
  GraduationCap,
  MessageCircle,
  Sparkles,
  UsersRound
} from "lucide-react";
import { PostCard } from "@/components/blog/post-card";
import { Header } from "@/components/marketing/header";
import { LeadForm } from "@/components/marketing/lead-form";
import { Section } from "@/components/marketing/section";
import { guides, posts, services } from "@/lib/content";
import { siteConfig } from "@/config/site";

const audiences = [
  {
    title: "Подростку",
    text: "Понять свои сильные стороны, попробовать проекты и собрать историю, которую не стыдно показать."
  },
  {
    title: "Родителям",
    text: "Видеть план, сроки, логику решений и не превращать развитие ребенка в бесконечный список кружков."
  }
];

const approach = [
  [Compass, "Стратегия", "Сначала разбираемся, куда подросток хочет двигаться и какие шаги действительно имеют смысл."],
  [ClipboardList, "План", "Собираем понятную дорожную карту: учеба, проекты, дедлайны, портфолио, коммуникация с семьей."],
  [CalendarCheck, "Сопровождение", "Держим темп, помогаем с решениями и не даем хорошим идеям раствориться в занятости."],
  [GraduationCap, "Упаковка", "Формулируем опыт подростка так, чтобы он звучал ясно, честно и убедительно."]
];

export default function HomePage() {
  const featuredServices = services.slice(0, 3);
  const featuredGuides = guides.slice(0, 3);

  return (
    <>
      <Header />
      <main>
        <section className="relative overflow-hidden border-b border-white/10 bg-navy-950">
          <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(4,11,22,0.98)_0%,rgba(10,26,47,0.92)_46%,rgba(201,162,75,0.12)_100%)]" />
          <div className="relative mx-auto grid min-h-[calc(100vh-5rem)] w-full max-w-7xl items-center gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:px-8">
            <div>
              <p className="mb-6 inline-flex items-center gap-2 rounded-lg border border-gold-400/30 bg-gold-400/10 px-3 py-2 text-sm font-semibold text-gold-300">
                <Sparkles size={16} aria-hidden="true" />
                Не курсы. Персональная траектория для подростка.
              </p>
              <h1 className="font-display text-5xl font-extrabold leading-none text-porcelain sm:text-6xl lg:text-7xl">
                PrimeTeens
              </h1>
              <p className="mt-6 max-w-3xl text-2xl font-semibold leading-tight text-champagne sm:text-4xl">
                Помогаем подросткам раскрыть потенциал и собрать сильную историю для будущего.
              </p>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-muted">
                Работаем с подростками 13-17 лет и родителями: стратегия, полное сопровождение, проекты, портфолио, события и подготовка к важным образовательным решениям.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="/services"
                  className="focus-ring inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-gold-500 px-5 font-semibold text-navy-950 transition hover:bg-gold-400"
                >
                  Посмотреть услуги
                  <ArrowRight size={18} aria-hidden="true" />
                </Link>
                <Link
                  href="#contact"
                  className="focus-ring inline-flex h-12 items-center justify-center gap-2 rounded-lg border border-white/[0.16] px-5 font-semibold text-porcelain transition hover:border-gold-400/70 hover:text-gold-300"
                >
                  Обсудить ситуацию
                  <MessageCircle size={18} aria-hidden="true" />
                </Link>
              </div>
            </div>

            <div className="relative min-h-[28rem]">
              <Image
                src="/prime-teens-logo.png"
                alt="PrimeTeens"
                width={560}
                height={560}
                className="absolute right-0 top-0 h-64 w-64 rounded-lg object-cover opacity-20 sm:h-80 sm:w-80 lg:h-96 lg:w-96"
                priority
              />
              <div className="absolute bottom-0 left-0 right-0 grid gap-3">
                {[
                  ["01", "Личная стратегия", "понять цели и ближайшие шаги"],
                  ["02", "Проекты и опыт", "сделать то, что можно показать"],
                  ["03", "Портфолио", "упаковать факты в сильную историю"]
                ].map(([step, title, text]) => (
                  <div key={step} className="glass rounded-lg p-5">
                    <div className="flex items-start gap-4">
                      <span className="gold-text font-display text-2xl font-extrabold">{step}</span>
                      <div>
                        <h2 className="font-display text-xl font-bold text-porcelain">{title}</h2>
                        <p className="mt-1 text-sm leading-6 text-muted">{text}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <Section
          id="services"
          tone="light"
          eyebrow="Услуги"
          title="Не все услуги финально упакованы, но направление уже ясно"
          subtitle="PrimeTeens строится не вокруг одного продукта. Мы помогаем семье понять ситуацию подростка и выбрать формат работы: от разовой консультации до полного сопровождения."
        >
          <div className="grid gap-4 lg:grid-cols-3">
            {featuredServices.map((service) => (
              <article key={service.slug} className="rounded-lg border border-navy-900/10 bg-white p-6 shadow-sm">
                <p className="mb-3 text-sm font-semibold text-gold-500">{service.kicker}</p>
                <h3 className="font-display text-2xl font-bold">{service.title}</h3>
                <p className="mt-4 text-sm leading-6 text-navy-700">{service.description}</p>
                <Link href={`/services#${service.slug}`} className="focus-ring mt-6 inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-gold-500">
                  Подробнее
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
              </article>
            ))}
          </div>
        </Section>

        <Section
          id="about"
          eyebrow="О нас"
          title="Мы помогаем подростку не потеряться между ожиданиями, возможностями и дедлайнами"
          subtitle="У подростка часто есть интересы, энергия и потенциал, но нет структуры. У родителя есть тревога и желание помочь, но не всегда понятно, где поддержка, а где давление. PrimeTeens соединяет эти две стороны."
        >
          <div className="grid gap-4 md:grid-cols-2">
            {audiences.map((item) => (
              <article key={item.title} className="glass rounded-lg p-6">
                <UsersRound className="mb-5 text-gold-300" size={28} aria-hidden="true" />
                <h3 className="font-display text-2xl font-bold">{item.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted">{item.text}</p>
              </article>
            ))}
          </div>
        </Section>

        <Section
          id="approach"
          tone="light"
          eyebrow="Подход"
          title="Сначала смысл, потом активности"
          subtitle="Мы не набрасываем подростку случайные кружки и конкурсы. Сначала собираем контекст, а потом выбираем действия, которые действительно усиливают его историю."
        >
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {approach.map(([Icon, title, text]) => (
              <article key={String(title)} className="rounded-lg border border-navy-900/10 bg-white p-5 shadow-sm">
                <Icon className="mb-5 text-gold-500" size={28} aria-hidden="true" />
                <h3 className="font-display text-xl font-bold">{String(title)}</h3>
                <p className="mt-3 text-sm leading-6 text-navy-700">{String(text)}</p>
              </article>
            ))}
          </div>
        </Section>

        <Section
          id="guides"
          eyebrow="Гайды"
          title="Гайды - это отдельная библиотека, а не смысл компании"
          subtitle="Они помогают разобраться в отдельных темах и могут быть первым касанием с PrimeTeens. Основная работа начинается там, где нужен личный контекст."
        >
          <div className="grid gap-4 md:grid-cols-3">
            {featuredGuides.map((guide) => (
              <article key={guide.slug} className="glass rounded-lg p-5">
                <BookOpen className="mb-5 text-gold-300" size={28} aria-hidden="true" />
                <p className="mb-2 text-sm font-semibold text-gold-300">{guide.topic}</p>
                <h3 className="font-display text-xl font-bold">{guide.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted">{guide.description}</p>
              </article>
            ))}
          </div>
          <Link href="/guides" className="focus-ring mt-8 inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-gold-300">
            Все гайды
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </Section>

        <Section
          id="blog-preview"
          tone="light"
          eyebrow="Блог"
          title="Блог - отдельно: мысли, разборы и практические материалы"
          subtitle="Здесь можно читать про подростковое развитие, портфолио, проекты, образовательные решения и опыт PrimeTeens."
        >
          <div className="grid gap-4 md:grid-cols-3">
            {posts.map((post) => (
              <PostCard key={post.slug} post={post} />
            ))}
          </div>
          <Link href="/blog" className="focus-ring mt-8 inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-gold-500">
            Открыть блог
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </Section>

        <Section
          id="contact"
          eyebrow="Контакт"
          title="Расскажите, что сейчас непонятно"
          subtitle="Можно начать не с выбора услуги, а с разговора. Опишите ситуацию - мы подскажем, какой формат PrimeTeens подойдет лучше."
        >
          <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
            <div className="glass rounded-lg p-6">
              <CheckCircle2 className="mb-5 text-gold-300" size={32} aria-hidden="true" />
              <h3 className="font-display text-2xl font-bold">Сайт будет расширяться вместе с продуктами</h3>
              <p className="mt-4 text-sm leading-6 text-muted">
                Сейчас мы разделили основные направления: услуги, гайды, блог и информацию о PrimeTeens. Детальные пакеты услуг можно спокойно доупаковать позже.
              </p>
            </div>
            <LeadForm />
          </div>
        </Section>

        <footer className="border-t border-white/10 bg-navy-950">
          <div className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-10 text-sm text-muted sm:px-6 lg:grid-cols-[1fr_auto] lg:px-8">
            <div>
              <p className="font-display text-xl font-bold text-porcelain">{siteConfig.name}</p>
              <p className="mt-2 max-w-xl">{siteConfig.description}</p>
            </div>
            <div className="flex flex-wrap gap-4">
              <a className="focus-ring rounded-lg hover:text-gold-300" href={siteConfig.contacts.telegram}>
                Telegram
              </a>
              <a className="focus-ring rounded-lg hover:text-gold-300" href={siteConfig.contacts.instagram}>
                Instagram
              </a>
              <a className="focus-ring rounded-lg hover:text-gold-300" href={`mailto:${siteConfig.contacts.email}`}>
                Email
              </a>
            </div>
          </div>
        </footer>
      </main>
    </>
  );
}
