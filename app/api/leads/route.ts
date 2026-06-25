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

  // TODO: persist into Supabase/Postgres `Lead` and trigger an email with the requested guide.
  return NextResponse.json({
    ok: true,
    message: "Спасибо. Мы приняли заявку и подготовим письмо с PDF-гайдом."
  });
}
