import type { Metadata } from "next";
import { Inter, Unbounded } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["cyrillic", "latin"],
  variable: "--font-inter",
  display: "swap"
});

const unbounded = Unbounded({
  subsets: ["cyrillic", "latin"],
  weight: ["500", "600", "700", "800"],
  variable: "--font-display",
  display: "swap"
});

export const metadata: Metadata = {
  metadataBase: new URL("https://primeteens.kz"),
  title: {
    default: "PrimeTeens - сопровождение поступления в вузы",
    template: "%s | PrimeTeens"
  },
  description:
    "PrimeTeens ведёт школьников и студентов от профориентации до зачисления в зарубежные и казахстанские вузы: стратегия, документы и личный куратор на каждом шаге.",
  openGraph: {
    title: "PrimeTeens - от профориентации до зачисления",
    description:
      "Профориентация, документы, эссе и куратор, который ведёт студента и родителей до самого зачисления.",
    images: ["/prime-teens-logo.png"],
    locale: "ru_KZ",
    type: "website"
  }
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body className={`${inter.variable} ${unbounded.variable} font-sans antialiased`}>
        {children}
      </body>
    </html>
  );
}
