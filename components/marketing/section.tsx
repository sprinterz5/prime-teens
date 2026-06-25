import type { ReactNode } from "react";

type SectionProps = {
  id?: string;
  eyebrow?: string;
  title?: string;
  subtitle?: string;
  children: ReactNode;
  tone?: "dark" | "light";
};

export function Section({ id, eyebrow, title, subtitle, children, tone = "dark" }: SectionProps) {
  const isLight = tone === "light";

  return (
    <section id={id} className={isLight ? "bg-porcelain text-navy-900" : "bg-transparent text-porcelain"}>
      <div className="mx-auto w-full max-w-7xl px-4 py-16 sm:px-6 sm:py-20 lg:px-8">
        {(eyebrow || title || subtitle) && (
          <div className="mb-10 max-w-3xl">
            {eyebrow && (
              <p className={isLight ? "mb-3 text-sm font-semibold text-gold-500" : "mb-3 text-sm font-semibold text-gold-300"}>
                {eyebrow}
              </p>
            )}
            {title && <h2 className="font-display text-3xl font-extrabold leading-tight sm:text-4xl">{title}</h2>}
            {subtitle && (
              <p className={isLight ? "mt-4 text-base leading-7 text-navy-700" : "mt-4 text-base leading-7 text-muted"}>
                {subtitle}
              </p>
            )}
          </div>
        )}
        {children}
      </div>
    </section>
  );
}
