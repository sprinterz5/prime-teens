import { NextResponse } from "next/server";
import { leadSchema } from "@/lib/leads";

export async function POST(request: Request) {
  const payload = await request.json().catch(() => null);
  const parsed = leadSchema.safeParse(payload);

  if (!parsed.success) {
    return NextResponse.json(
      {
        ok: false,
        message: parsed.error.issues[0]?.message ?? "Проверьте данные формы"
      },
      { status: 400 }
    );
  }

  if (parsed.data.website) {
    return NextResponse.json({ ok: true, message: "Спасибо, заявка принята." });
  }

  // TODO: persist into Postgres `Lead` (prisma) and hand off to the CRM (sales queue / assigned rep).
  return NextResponse.json({
    ok: true,
    message: "Спасибо. Мы приняли заявку и свяжемся с вами."
  });
}
