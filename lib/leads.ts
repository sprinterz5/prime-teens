import { z } from "zod";

export const leadSchema = z.object({
  email: z.string().trim().email("Введите корректный email"),
  role: z.enum(["parent", "teen"]).default("parent"),
  guideRequested: z.string().trim().min(2).default("strong-portfolio"),
  consent: z.literal(true, {
    errorMap: () => ({ message: "Нужно согласие на обработку данных" })
  }),
  website: z.string().max(0).optional()
});

export type LeadInput = z.infer<typeof leadSchema>;
