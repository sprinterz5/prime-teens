import Image from "next/image";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { MobileNav } from "@/components/marketing/mobile-nav";
import { siteConfig } from "@/config/site";

export function Header() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-navy-950/86 backdrop-blur-xl">
      <div className="mx-auto flex h-20 w-full max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="focus-ring flex items-center gap-3 rounded-lg">
          <Image
            src="/prime-teens-logo.png"
            alt="PrimeTeens"
            width={48}
            height={48}
            className="h-12 w-12 rounded-lg object-cover"
            priority
          />
          <div className="leading-tight">
            <div className="font-display text-base font-semibold text-porcelain">PrimeTeens</div>
            <div className="hidden text-xs text-muted sm:block">Сопровождение поступления</div>
          </div>
        </Link>

        <nav className="hidden items-center gap-7 text-sm text-muted md:flex" aria-label="Главное меню">
          {siteConfig.nav.map((item) => (
            <Link key={item.href} href={item.href} className="focus-ring rounded-lg transition hover:text-champagne">
              {item.label}
            </Link>
          ))}
        </nav>

        <Link href="/#contact" className="btn btn-primary focus-ring hidden h-11 md:inline-flex">
          Записаться
          <ArrowRight size={17} aria-hidden="true" />
        </Link>

        <MobileNav />
      </div>
    </header>
  );
}
