# PrimeTeens

Next.js MVP for the PrimeTeens public platform: company landing page, services, guides, blog seed content, lead form API, sitemap/RSS, and Prisma schema for the future platform.

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
- `/blog/tag/[tag]` - track filter
- `/blog/rss.xml` - RSS feed
- `/api/leads` - lead capture endpoint
- `/sitemap.xml` and `/robots.txt`

## Next Steps

- Finalize service packages, prices, duration, and sales copy.
- Connect `/api/leads` to Supabase/PostgreSQL and email delivery.
- Replace local `lib/content.ts` posts with DB-backed content and a studio UI.
- Add kk/en translations once Russian copy is approved.
