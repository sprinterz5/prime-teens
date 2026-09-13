import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  CalendarClock,
  ChevronDown,
  ClipboardCheck,
  Download,
  FileLock2,
  GraduationCap,
  MessageCircle,
  Route,
  ScrollText,
  Signature,
  Sparkles,
  UsersRound
} from "lucide-react";
import { PostCard } from "@/components/blog/post-card";
import { Footer } from "@/components/marketing/footer";
import { Header } from "@/components/marketing/header";
import { LeadForm } from "@/components/marketing/lead-form";
import { Section } from "@/components/marketing/section";
import { guides, posts, services } from "@/lib/content";

const audiences = [
  {
    title: "Родителям",
    text: "Видеть прогресс, сроки и договор в одном месте — без хаоса из десятка чатов и разрозненных советов."
  },
  {
    title: "Студентам",
    text: "Понятный план: какие вузы, какие документы, к какому сроку — и куратор, который держит темп."
  }
];

const funnel = [
  [Route, "Профориентация", "Тестируем интересы и способности, разбираем профиль — получаете реалистичный список направлений и стран."],
  [ClipboardCheck, "Стратегия", "Собираем короткий список вузов, сроки подачи и бюджет — понятный план на сезон."],
  [Signature, "Документы и договор", "Эссе, рекомендации, перевод документов и договор с фиксацией этапов и оплаты."],
  [GraduationCap, "Куратор до зачисления", "Куратор ведёт коммуникацию с вузами и держит дедлайны до финального решения."]
];

const trustPoints = [
  [UsersRound, "Один куратор", "Ведёт студента от старта до зачисления — не десяток разных менеджеров."],
  [ScrollText, "Договор", "Этапы, сроки и оплата фиксируются в договоре — без устных договорённостей."],
  [ClipboardCheck, "Прозрачность", "Родители видят прогресс, а не гадают, что происходит с заявкой."],
  [FileLock2, "Защита данных", "Работаем по закону РК о персональных данных, с согласием родителя для несовершеннолетних."]
];

const faq = [
  {
    q: "Сколько это стоит?",
    a: "Стоимость зависит от формата и объёма работы и фиксируется в договоре — после профориентации или первого разговора. Начать можно с обсуждения ситуации, а не с оплаты."
  },
  {
    q: "С какими странами и вузами вы работаете?",
    a: "Сопровождаем поступление как в зарубежные, так и в казахстанские вузы. Конкретные направления и список вузов собираются на профориентации под цели и профиль студента."
  },
  {
    q: "Что если английский ещё слабый?",
    a: "Профориентация показывает текущий уровень и помогает встроить подготовку к международным экзаменам (IELTS, SAT, TOEFL) в общий график поступления, а не готовить их отдельно от дедлайнов."
  },
  {
    q: "Насколько безопасны данные студента?",
    a: "Работаем по договору и с согласием на обработку персональных данных. Для студентов младше 18 лет требуется согласие родителя."
  },
  {
    q: "Можно начать без профориентации?",
    a: "Да. Можно начать с разговора о ситуации студента — вместе решим, нужна ли профориентация или сразу подойдёт полное сопровождение."
  }
];

export default function HomePage() {
  const featuredServices = services.slice(0, 3);
  const featuredGuides = guides.slice(0, 3);

  return (
    <>
      <Header />
      <main>
        <section className="bg-grid relative overflow-hidden border-b border-white/10 bg-navy-950">
          <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(4,11,22,0.98)_0%,rgba(10,26,47,0.92)_46%,rgba(201,162,75,0.12)_100%)]" />
          <svg
            viewBox="0 0 200 200"
            aria-hidden="true"
            className="pointer-events-none absolute -right-10 -top-10 h-56 w-56 text-gold-400/50 sm:h-72 sm:w-72"
          >
            <path
              d="M100 15 L110 90 L185 100 L110 110 L100 185 L90 110 L15 100 L90 90 Z"
              fill="currentColor"
            />
          </svg>
          <svg
            viewBox="0 0 200 200"
            aria-hidden="true"
            className="pointer-events-none absolute right-28 top-40 h-10 w-10 text-gold-300/40 sm:right-36"
          >
            <path
              d="M100 15 L110 90 L185 100 L110 110 L100 185 L90 110 L15 100 L90 90 Z"
              fill="currentColor"
            />
          </svg>

          <div className="relative mx-auto grid min-h-[calc(100vh-5rem)] w-full max-w-7xl items-center gap-12 px-4 py-12 sm:px-6 lg:grid-cols-[1.1fr_0.9fr] lg:px-8">
            <div>
              <p className="mb-6 inline-flex items-center gap-2 rounded-lg border border-gold-400/30 bg-gold-400/10 px-3 py-2 text-sm font-semibold text-gold-300">
                <Sparkles size={16} aria-hidden="true" />
                Не курсы. Личное сопровождение поступления от куратора.
              </p>
              <h1 className="font-display text-4xl font-bold leading-[1.05] text-porcelain sm:text-5xl lg:text-6xl">
                От профориентации <span className="gold-text">до зачисления</span> — в одном окне для студента и родителей.
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-muted">
                Сопровождаем школьников и студентов при поступлении в зарубежные и казахстанские вузы: стратегия, документы, эссе, договор и куратор, который держит сроки.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href="/services" className="btn btn-primary focus-ring">
                  Посмотреть услуги
                  <ArrowRight size={18} aria-hidden="true" />
                </Link>
                <Link href="#contact" className="btn btn-secondary focus-ring">
                  Записаться на профориентацию
                  <MessageCircle size={18} aria-hidden="true" />
                </Link>
              </div>
              <div className="mt-8 flex flex-wrap gap-3 text-xs text-muted">
                {audiences.map((item) => (
                  <Link
                    key={item.title}
                    href="#about"
                    className="focus-ring rounded-lg border border-white/[0.12] bg-white/[0.04] px-3 py-2 font-semibold text-champagne transition hover:border-gold-400/60 hover:text-gold-300"
                  >
                    {item.title}
                  </Link>
                ))}
                <span className="inline-flex items-center rounded-lg border border-white/[0.08] px-3 py-2">
                  Казахстан · зарубежные и местные вузы
                </span>
              </div>
            </div>

            <div className="relative min-h-[24rem]">
              <div className="grid gap-3">
                {[
                  ["01", "Профориентация", "понять сильные стороны и направления"],
                  ["02", "Стратегия и вузы", "собрать реалистичный список и сроки"],
                  ["03", "Куратор до зачисления", "документы, договор, дедлайны"]
                ].map(([step, title, text]) => (
                  <div key={step} className="glass card-hover rounded-lg p-5">
                    <div className="flex items-start gap-4">
                      <span className="gold-text font-display text-2xl font-bold">{step}</span>
                      <div>
                        <h2 className="font-display text-lg font-semibold text-porcelain">{title}</h2>
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
          id="how"
          tone="light"
          eyebrow="Как это работает"
          title="Один путь: от профориентации до зачисления"
          subtitle="Каждый этап фиксируется — семья видит прогресс, а не догадывается, что происходит с заявкой."
        >
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {funnel.map(([Icon, title, text]) => (
              <article key={String(title)} className="card-hover rounded-lg border border-navy-900/10 bg-white p-5 shadow-sm">
                <span className="icon-badge icon-badge-light mb-5">
                  <Icon size={22} aria-hidden="true" />
                </span>
                <h3 className="font-display text-lg font-semibold">{String(title)}</h3>
                <p className="mt-3 text-sm leading-6 text-navy-700">{String(text)}</p>
              </article>
            ))}
          </div>
        </Section>

        <Section
          id="services"
          eyebrow="Услуги"
          title="Ядро одно: студент не остаётся один на один с процессом поступления"
          subtitle="Один куратор ведёт весь путь. Начните с профориентации — или сразу берите полное сопровождение, если направление уже понятно."
        >
          <div className="grid gap-4 lg:grid-cols-3">
            {featuredServices.map((service) => (
              <article key={service.slug} className="glass card-hover rounded-lg p-6">
                <p className="mb-3 text-sm font-semibold text-gold-300">{service.kicker}</p>
                <h3 className="font-display text-xl font-semibold text-porcelain">{service.title}</h3>
                <p className="mt-4 text-sm leading-6 text-muted">{service.description}</p>
                <Link href={`/services#${service.slug}`} className="focus-ring mt-6 inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-gold-300">
                  Подробнее
                  <ArrowRight size={16} aria-hidden="true" />
                </Link>
              </article>
            ))}
          </div>
        </Section>

        <Section
          id="about"
          tone="light"
          eyebrow="О нас"
          title="Соединяем ожидания родителей, сроки вузов и реальные возможности студента"
          subtitle="У студента часто есть цель, но нет структуры. У родителя — тревога за сроки и деньги. PrimeTeens берёт на себя координацию между семьёй, куратором и вузами."
        >
          <div className="grid gap-4 md:grid-cols-2">
            {audiences.map((item) => (
              <article key={item.title} className="card-hover rounded-lg border border-navy-900/10 bg-white p-6 shadow-sm">
                <span className="icon-badge icon-badge-light mb-5">
                  <UsersRound size={22} aria-hidden="true" />
                </span>
                <h3 className="font-display text-xl font-semibold">{item.title}</h3>
                <p className="mt-3 text-sm leading-6 text-navy-700">{item.text}</p>
              </article>
            ))}
          </div>
        </Section>

        <Section eyebrow="Доверие" title="Прозрачность вместо обещаний">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {trustPoints.map(([Icon, title, text]) => (
              <article key={String(title)} className="glass card-hover rounded-lg p-5">
                <span className="icon-badge mb-5">
                  <Icon size={20} aria-hidden="true" />
                </span>
                <h3 className="font-display text-base font-semibold text-porcelain">{String(title)}</h3>
                <p className="mt-2 text-sm leading-6 text-muted">{String(text)}</p>
              </article>
            ))}
          </div>
        </Section>

        <Section
          id="guides"
          tone="light"
          eyebrow="Ресурсы"
          title="Гайды серии «Сильное портфолио» — бесплатно, сразу PDF"
          subtitle="Они помогают быстро разобраться в отдельных темах. Полноценная стратегия строится на профориентации и работе с куратором."
        >
          <div className="grid gap-4 md:grid-cols-3">
            {featuredGuides.map((guide) => (
              <a
                key={guide.slug}
                href={guide.file}
                download
                className="card-hover focus-ring group block rounded-lg border border-navy-900/10 bg-white p-5 shadow-sm"
              >
                <span className="icon-badge icon-badge-light mb-5">
                  <BookOpen size={20} aria-hidden="true" />
                </span>
                <p className="mb-2 text-sm font-semibold text-gold-500">{guide.topic}</p>
                <h3 className="font-display text-lg font-semibold">{guide.title}</h3>
                <p className="mt-3 text-sm leading-6 text-navy-700">{guide.description}</p>
                <p className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-gold-500 group-hover:text-gold-400">
                  <Download size={15} aria-hidden="true" />
                  Скачать PDF
                </p>
              </a>
            ))}
          </div>
          <Link href="/guides" className="focus-ring mt-8 inline-flex items-center gap-2 rounded-lg text-sm font-semibold text-gold-500">
            Все материалы
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </Section>

        <Section
          id="blog-preview"
          eyebrow="Блог"
          title="Блог - разборы, чек-листы и истории поступления"
          subtitle="Про профориентацию, документы, экзамены, стипендии и то, как устроено сопровождение изнутри."
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

        <Section tone="light" eyebrow="Вопросы" title="Частые вопросы">
          <div className="grid gap-3">
            {faq.map((item) => (
              <details key={item.q} className="faq-item rounded-lg border border-navy-900/10 bg-white p-5 shadow-sm">
                <summary className="flex items-center justify-between gap-4 font-display text-base font-semibold text-navy-900">
                  {item.q}
                  <ChevronDown className="faq-chevron shrink-0 text-gold-500" size={20} aria-hidden="true" />
                </summary>
                <p className="mt-3 text-sm leading-6 text-navy-700">{item.a}</p>
              </details>
            ))}
          </div>
        </Section>

        <Section
          id="contact"
          eyebrow="Контакт"
          title="Запишитесь на профориентацию"
          subtitle="Можно начать не с выбора пакета услуг, а с разговора. Опишите ситуацию студента — мы предложим формат: профориентацию, консультацию или полное сопровождение."
        >
          <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
            <div className="glass rounded-lg p-6">
              <span className="icon-badge mb-5">
                <CalendarClock size={22} aria-hidden="true" />
              </span>
              <h3 className="font-display text-xl font-semibold">Что происходит после заявки</h3>
              <p className="mt-4 text-sm leading-6 text-muted">
                Менеджер свяжется в течение рабочего дня, уточнит ситуацию студента и предложит следующий шаг — профориентацию, консультацию или сразу пакет полного сопровождения.
              </p>
            </div>
            <LeadForm />
          </div>
        </Section>

        <Footer />
      </main>
    </>
  );
}
