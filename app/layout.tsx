import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["cyrillic", "latin"],
  variable: "--font-inter",
  display: "swap"
});

const manrope = Manrope({
  subsets: ["cyrillic", "latin"],
  variable: "--font-manrope",
  display: "swap"
});

export const metadata: Metadata = {
  metadataBase: new URL("https://primeteens.kz"),
  title: {
    default: "PrimeTeens - сильное портфолио для подростков",
    template: "%s | PrimeTeens"
  },
  description:
    "PrimeTeens помогает подросткам 13-17 лет в Казахстане собрать портфолио для поступления в топовые вузы мира.",
  openGraph: {
    title: "PrimeTeens - покажи лучшее в себе",
    description:
      "Гайды, события и менторское сопровождение для сильного подросткового портфолио.",
    images: ["/prime-teens-logo.png"],
    locale: "ru_KZ",
    type: "website"
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body className={`${inter.variable} ${manrope.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
