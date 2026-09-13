import Link from "next/link";
import { siteConfig } from "@/config/site";

export function Footer() {
  return (
    <footer className="border-t border-white/10 bg-navy-950">
      <div className="mx-auto grid w-full max-w-7xl gap-8 px-4 py-10 text-sm text-muted sm:px-6 lg:grid-cols-[1fr_auto_auto] lg:px-8">
        <div>
          <p className="font-display text-lg font-semibold text-porcelain">{siteConfig.name}</p>
          <p className="mt-2 max-w-xl">{siteConfig.description}</p>
        </div>

        <div className="flex flex-wrap gap-4">
          {siteConfig.nav.map((item) => (
            <Link key={item.href} href={item.href} className="focus-ring rounded-lg hover:text-gold-300">
              {item.label}
            </Link>
          ))}
          <Link href="/privacy" className="focus-ring rounded-lg hover:text-gold-300">
            Конфиденциальность
          </Link>
        </div>

        <div className="flex flex-wrap gap-4">
          <a className="focus-ring rounded-lg hover:text-gold-300" href={siteConfig.contacts.telegram}>
            Telegram
          </a>
          <a className="focus-ring rounded-lg hover:text-gold-300" href={siteConfig.contacts.instagram}>
            Instagram
          </a>
          <a className="focus-ring rounded-lg hover:text-gold-300" href={`mailto:${siteConfig.contacts.email}`}>
            Почта
          </a>
        </div>
      </div>
    </footer>
  );
}
