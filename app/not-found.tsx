import Link from "next/link";
import { ArrowRight, House } from "lucide-react";
import { Header } from "@/components/marketing/header";

export default function NotFound() {
  return (
    <>
      <Header />
      <main className="bg-grid flex min-h-[calc(100vh-5rem)] items-center justify-center bg-navy-950 px-4 py-20 text-center">
        <div>
          <p className="eyebrow eyebrow-center mb-6 justify-center">Страница не найдена</p>
          <h1 className="font-display text-6xl font-bold text-porcelain sm:text-7xl">404</h1>
          <p className="mx-auto mt-4 max-w-md text-base leading-7 text-muted">
            Такой страницы нет — возможно, ссылка устарела. Вернитесь на главную или посмотрите услуги.
          </p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/" className="btn btn-primary focus-ring">
              <House size={18} aria-hidden="true" />
              На главную
            </Link>
            <Link href="/services" className="btn btn-secondary focus-ring">
              Посмотреть услуги
              <ArrowRight size={18} aria-hidden="true" />
            </Link>
          </div>
        </div>
      </main>
    </>
  );
}
