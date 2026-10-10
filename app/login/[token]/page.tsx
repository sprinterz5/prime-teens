import type { Metadata } from "next";
import { LinkLogin } from "./link-login";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Вход на платформу", robots: { index: false } };

export default async function LinkLoginPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-navy-950 px-4 text-center text-white">
      <LinkLogin token={token} />
    </main>
  );
}
