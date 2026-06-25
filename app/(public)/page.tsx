import Image from "next/image";
import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  FileText,
  GraduationCap,
  ShieldCheck,
  Sparkles,
  UsersRound
} from "lucide-react";
import { Header } from "@/components/marketing/header";
import { LeadForm } from "@/components/marketing/lead-form";
import { Section } from "@/components/marketing/section";
import { PostCard } from "@/components/blog/post-card";
import { posts, tracks } from "@/lib/content";
import { siteConfig } from "@/config/site";

const proof = [
  {
    title: "Драма-клуб",
    text: "Из интереса к сцене - в регулярный клуб с ролями, афишами и итоговым выступлением."
  },
  {
    title: "EcoHackathon",
    text: "Команда формулирует проблему, собирает прототип и презентует решение перед аудиторией."
  },
  {
    title: "IBO-медаль",
    text: "Олимпиадный трек превращает подготовку в понятную историю роста и дисциплины."
  }
];

const faq = [
  {
    q: "С чего начать, если у ребенка пока нет достижений?",
    a: "С короткого диагностического маршрута: интересы, свободное время, сильные предметы и один проект на 4-6 недель."
  },
  {
    q: "Нужен ли большой бюджет?",
    a: "Нет. Клуб, волонтерство, школьное исследование и часть олимпиад можно запускать с бюджетом 0 тенге."
  },
  {
    q: "Это для родителей или для подростков?",
    a: "Для обоих. Родитель видит стратегию и безопасность, подросток получает понятные шаги и зону ответственности."
  },
  {
    q: "Что будет в гайде?",
    a: "Треки портфолио, примеры первых шагов, чеклист доказательств и идеи активностей для Казахстана."
  }
];

export default function HomePage() {
  return (
    <>
      <Header />
      <main>
        <section className="relative overflow-hidden border-b border-white/10">
          <div className="absolute inset-0 bg-[linear-gradient(115deg,rgba(10,26,47,0.98)_0%,rgba(4,11,22,0.88)_54%,rgba(201,162,75,0.10)_100%)]" />
          <div className="relative mx-auto grid min-h-[calc(100vh-5rem)] w-full max-w-7xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:px-8">
            <div>
              <p className="mb-5 inline-flex items-center gap-2 rounded-lg border border-gold-400/30 bg-gold-400/10 px-3 py-2 text-sm font-semibold text-gold-300">
                <Sparkles size={16} aria-hidden="true" />
                Для подростков 13-17 лет в Казахстане
              </p>
              <h1 className="font-display text-5xl font-extrabold leading-none text-porcelain sm:text-6xl lg:text-7xl">
                PrimeTeens
              </h1>
              <p className="mt-5 max-w-2xl text-2xl font-semibold leading-tight text-champagne sm:text-3xl">
                Покажи лучшее в себе
              </p>
              <p className="mt-5 max-w-2xl text-lg leading-8 text-muted">
                Помогаем подросткам собрать сильное портфолио для поступления в топовые вузы мира: через олимпиады, клубы, проекты, хакатоны и исследования.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link
                  href="#parents"
                  className="focus-ring inline-flex h-12 items-center justify-center gap-2 rounded-lg bg-gold-500 px-5 font-semibold text-navy-950 transition hover:bg-gold-400"
                >
                  Родителям
                  <ArrowRight size={18} aria-hidden="true" />
                </Link>
                <Link
                  href="#tracks"
                  className="focus-ring inline-flex h-12 items-center justify-center gap-2 rounded-lg border border-white/16 px-5 font-semibold text-porcelain transition hover:border-gold-400/70 hover:text-gold-300"
                >
                  Подросткам
                  <ChevronRight size={18} aria-hidden="true" />
                </Link>
              </div>
            </div>

            <div className="glass relative rounded-lg p-5 shadow-glow">
              <Image
                src="/prime-teens-logo.png"
                alt="Логотип PrimeTeens"
                width={640}
                height={640}
                className="mx-auto aspect-square w-full max-w-[30rem] rounded-lg object-cover"
                priority
              />
              <div className="mt-5 grid grid-cols-3 gap-3 text-center">
                {["Гайды", "События", "Менторы"].map((item) => (
                  <div key={item} className="rounded-lg border border-white/10 bg-white/5 px-3 py-4 text-sm font-semibold text-champagne">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <Section
          id="parents"
          eyebrow="Главный миф"
          title="Сильное портфолио не требует больших денег"
          subtitle="Часть самых сильных активностей начинается с нуля: школьный клуб, исследовательский вопрос, волонтерская инициатива или командный хакатон."
        >
          <div className="grid gap-4 md:grid-cols-3">
            {[
              ["0 ₸", "Можно стартовать без бюджета, если есть план, регулярность и доказательства результата."],
              ["6 недель", "Достаточно для первого цикла клуба, проекта или подготовки к стартовой олимпиаде."],
              ["2 входа", "Родитель видит стратегию, подросток понимает конкретные шаги и ответственность."]
            ].map(([number, text]) => (
              <div key={number} className="glass rounded-lg p-6">
                <div className="gold-text font-display text-4xl font-extrabold">{number}</div>
                <p className="mt-4 text-sm leading-6 text-muted">{text}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section
          id="tracks"
          eyebrow="Треки портфолио"
          title="Шесть направлений, из которых складывается сильная история"
          subtitle="Мы связываем интересы подростка с активностями, которые можно подтвердить фактами, ролями и результатами."
        >
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {tracks.map((track) => {
              const Icon = track.icon;
              return (
                <article key={track.slug} className="glass rounded-lg p-5">
                  <Icon className="mb-5 text-gold-300" size={28} aria-hidden="true" />
                  <p className="mb-2 text-sm font-semibold text-gold-300">{track.label}</p>
                  <h3 className="font-display text-xl font-bold text-porcelain">{track.title}</h3>
                  <p className="mt-3 text-sm leading-6 text-muted">{track.description}</p>
                  <p className="mt-4 border-t border-white/10 pt-4 text-sm leading-6 text-champagne">{track.detail}</p>
                </article>
              );
            })}
          </div>
        </Section>

        <Section
          id="process"
          tone="light"
          eyebrow="Как мы помогаем"
          title="От идеи до строки в портфолио"
          subtitle="PrimeTeens превращает хаотичные активности в понятный маршрут: выбрать трек, сделать проект, собрать доказательства и упаковать историю."
        >
          <div className="grid gap-4 lg:grid-cols-3">
            {[
              [FileText, "Гайды", "Чеклисты и маршруты по клубам, олимпиадам, проектам и портфолио без бюджета."],
              [UsersRound, "События", "Хакатоны и демо-дни, где подростки строят проект, а родители видят результат."],
              [GraduationCap, "Сопровождение", "Ментор помогает удержать темп, оформить роль и не потерять доказательства."]
            ].map(([Icon, title, text]) => (
              <div key={String(title)} className="rounded-lg border border-navy-900/10 bg-white p-6 shadow-sm">
                <Icon className="mb-5 text-gold-500" size={30} aria-hidden="true" />
                <h3 className="font-display text-xl font-bold">{String(title)}</h3>
                <p className="mt-3 text-sm leading-6 text-navy-700">{String(text)}</p>
              </div>
            ))}
          </div>
        </Section>

        <Section
          eyebrow="Истории из гайдов"
          title="Портфолио строится на действиях, которые можно показать"
          subtitle="Пока публичных отзывов нет, используем реальные сценарии из материалов PrimeTeens и оставляем место для будущих кейсов выпускников."
        >
          <div className="grid gap-4 md:grid-cols-3">
            {proof.map((item) => (
              <article key={item.title} className="glass rounded-lg p-6">
                <CheckCircle2 className="mb-5 text-gold-300" size={28} aria-hidden="true" />
                <h3 className="font-display text-xl font-bold">{item.title}</h3>
                <p className="mt-3 text-sm leading-6 text-muted">{item.text}</p>
              </article>
            ))}
          </div>
        </Section>

        <Section
          id="lead"
          eyebrow="Лид-магнит"
          title="Заберите гайд “Сильное портфолио”"
          subtitle="Отправим PDF с первыми шагами, треками и чеклистом доказательств. Сейчас форма сохраняет заявку через API, готовое место для подключения Supabase и email-рассылки уже заложено."
        >
          <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
            <div className="glass rounded-lg p-6">
              <ShieldCheck className="mb-5 text-gold-300" size={32} aria-hidden="true" />
              <h3 className="font-display text-2xl font-bold">Для родителя - стратегия. Для подростка - первый шаг.</h3>
              <p className="mt-4 text-sm leading-6 text-muted">
                Гайд помогает выбрать не “самую модную” активность, а ту, где подросток сможет показать инициативу, рост и результат.
              </p>
            </div>
            <LeadForm />
          </div>
        </Section>

        <Section
          id="blog-preview"
          eyebrow="Блог"
          title="Материалы из гайдов превращаются в статьи"
          subtitle="На старте блог работает на seed-данных. Следующий шаг - подключить БД и студию контента для SMM-автора."
        >
          <div className="grid gap-4 md:grid-cols-3">
            {posts.map((post) => (
              <PostCard key={post.slug} post={post} />
            ))}
          </div>
          <Link href="/blog" className="focus-ring mt-8 inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-gold-300">
            Открыть блог
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </Section>

        <Section id="faq" tone="light" eyebrow="FAQ" title="Вопросы перед стартом">
          <div className="grid gap-4 md:grid-cols-2">
            {faq.map((item) => (
              <article key={item.q} className="rounded-lg border border-navy-900/10 bg-white p-6 shadow-sm">
                <h3 className="font-display text-lg font-bold">{item.q}</h3>
                <p className="mt-3 text-sm leading-6 text-navy-700">{item.a}</p>
              </article>
            ))}
          </div>
        </Section>

        <footer className="border-t border-white/10 bg-navy-950">
          <div className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-10 text-sm text-muted sm:px-6 lg:grid-cols-[1fr_auto] lg:px-8">
            <div>
              <p className="font-display text-xl font-bold text-porcelain">{siteConfig.name}</p>
              <p className="mt-2 max-w-xl">{siteConfig.slogan}</p>
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
