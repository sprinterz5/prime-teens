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
    default: "PrimeTeens - сопровождение поступления в вузы",
    template: "%s | PrimeTeens"
  },
  description:
    "PrimeTeens сопровождает школьников и студентов при поступлении в зарубежные и казахстанские вузы: ассессмент, стратегия, документы и куратор до зачисления.",
  openGraph: {
    title: "PrimeTeens - от ассессмента до зачисления",
    description:
      "Профориентационный ассессмент, документы, эссе и куратор, который ведёт студента и родителей до зачисления.",
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
