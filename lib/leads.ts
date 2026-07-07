import { z } from "zod";

export const leadSchema = z.object({
  name: z.string().trim().min(2, "Введите имя"),
  contact: z.string().trim().min(5, "Укажите телефон или email"),
  role: z.enum(["parent", "student"]).default("parent"),
  interest: z.string().trim().min(2).default("assessment"),
  consent: z.literal(true, {
    errorMap: () => ({ message: "Нужно согласие на обработку данных" })
  }),
  website: z.string().max(0).optional()
});

export type LeadInput = z.infer<typeof leadSchema>;
