# PrimeTeens

Next.js MVP for the PrimeTeens admissions-support platform: company landing page, services, guides, blog seed content, lead form API, sitemap/RSS, and a Prisma schema scoped to what this web app owns (portal auth + site lead capture). The full CRM domain (deals, contracts, payments, curators) is designed in `PLAN.md` §6 for a future Spring Boot service, not modeled here.

## Stack

- Next.js 15 App Router
- TypeScript
- Tailwind CSS
- Prisma schema for PostgreSQL
- Local seed content for the first blog iteration

## Run

```bash
pnpm install
pnpm dev
```

Open http://127.0.0.1:3000.

## Build

```bash
pnpm build
```

## Current Routes

- `/` - landing page
- `/services` - services overview
- `/guides` - guides library
- `/about` - company/about page
- `/blog` - blog index
- `/blog/[slug]` - blog post
- `/blog/tag/[tag]` - category filter
- `/blog/rss.xml` - RSS feed
- `/api/leads` - lead capture endpoint
- `/sitemap.xml` and `/robots.txt`

## Next Steps

- Finalize service packages, prices, duration, and sales copy.
- Connect `/api/leads` to Postgres (`prisma`) and hand off to the CRM sales queue.
- Decide on the Deal/Contract/Payment backend (Spring Boot service per `PLAN.md` §8) before building the parent/student/curator kabinety.
- Replace local `lib/content.ts` posts with DB-backed content and a studio UI, if a content team is added.
- Add kk/en translations once Russian copy is approved.
