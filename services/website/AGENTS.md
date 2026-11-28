# fm01 Website Agent Guidelines (`AGENTS.md`)

Rules for AI agents and tools working on the fm01 website, `services/website/`. Production is https://fm01.bot; previews run on http://localhost:3007.

---

## 1. Stack

- **Framework:** Next.js 16 (App Router), React 19, TypeScript (`strict`).
- **Package manager:** pnpm (`pnpm-lock.yaml`, `pnpm-workspace.yaml`). Don't use npm or yarn.
- **Styling:** Tailwind CSS v4 through `@tailwindcss/postcss`. Theme tokens and custom utilities live in `_lib/css/globals.css`. There's no `tailwind.config`.
- **Theming:** `@teispace/next-themes` toggles a `.dark` class (light, dark, or system).
- **Content:** MDX legal documents rendered with `next-mdx-remote`.
- **Icons:** Font Awesome 7 (`@fortawesome/*`) and two custom SVG components in `_lib/svg/`.
- **Motion:** CSS transitions; `framer-motion` for section entrances.
- **Server:** plain `next dev` / `next start` on port 3007. There's no custom server: bot texts are bundled from `shared/` at build time, nothing is fetched at runtime.

## 2. Commands

| Task       | Command                                                                                     |
| ---------- | ------------------------------------------------------------------------------------------- |
| Dev server | `pnpm dev` (http://localhost:3007)                                                          |
| Build      | `pnpm build`                                                                                |
| Prod start | `pnpm start`                                                                                |
| Lint       | `pnpm lint`                                                                                 |
| Typecheck  | `pnpm typecheck`                                                                            |
| L10n check | `pnpm check:l10n`: showcase `botResponse`/`botText`/`botList` keys exist, en/hu parity      |
| Docker     | From the repo root: `docker compose --profile website up -d --build website` (or `docker build -f services/website/Dockerfile --target prod -t fm01-prod .`) |

Run lint, typecheck and (after touching `shared/localization/`) `pnpm check:l10n` before you call a change done. CI (`.github/workflows/website-ci.yml`) runs all three on PRs that touch `services/website/` or `shared/localization/`.

## 3. Layout

```
app/
├── layout.tsx, not-found.tsx
├── [lang]/                # every page is under a locale segment (en, hu)
│   ├── dictionaries.tsx   # loads the language JSON for a locale
│   ├── page.tsx           # home: Hero, Features showcase, PromotedServers, Premium
│   ├── features/          # /features page (own display type scale, see §6)
│   ├── legal/[[...doc]]/  # MDX legal docs (LEGAL_DATA maps slug → file in doc/<lang>/)
│   └── test/              # scratch page, not linked
└── api/
    ├── locale/            # locale negotiation
    └── og/                # Open Graph image route (reads from public/)
_lib/
├── components/            # Header, Footer, ThemeToggle, LangSelector, main/ (page sections), main/showcase/
├── css/                   # globals.css (tokens + utilities), features.css, legal.css
├── functions/             # botLocale.ts, responseExtractor.ts, metadata.ts (SITE_URL), paths.ts (SHARED_DIR), stats/promoted fetchers
├── svg/                   # Logo, Dashboard, Members glyphs as React components
└── types/                 # *Lang.tsx types for the dictionary shape
proxy.tsx                  # locale routing (Next 16 "proxy", formerly middleware), see below
```

**URLs carry no locale.** Public paths are bare (`/`, `/features`). `proxy.tsx` picks the locale from the `locale` cookie, then from `Accept-Language`, and rewrites the request internally to `app/[lang]/…`. Legacy `/hu/...` URLs redirect to the bare path and set the cookie. `x-locale` tells `app/layout.tsx` and `not-found.tsx` the locale. Never build links with a `/<lang>` prefix.

Path aliases (`tsconfig.json`): `@/*` → `./*`, `@lib/*` → `./_lib/*`, `@public/*` → `./public/*`, `@shared/*` → `../../shared/*`.

**The site reads from `shared/`.** `next.config.ts` sets `turbopack.root` and `outputFileTracingRoot` to the repo root; without that, imports from `../../shared` fail to resolve. The Docker build context is therefore the repo root, the image mirrors the repo layout (`/app/services/website` + `/app/shared/localization`), and `Dockerfile.dockerignore` allowlists only those two folders. Text is baked in at build time, so rebuild the image after changing `shared/localization/`.

## 4. Localization

- The site's text lives outside this folder, in `shared/localization/website/`, i.e. `en.json`, `<two_letter_language_id>.json` (imported via `@shared/localization/website/<lang>.json`) and the legal docs in `doc/<lang>/*.mdx` (read at runtime through `WEBSITE_L10N_DIR` in `_lib/functions/paths.ts`). Files in `doc/<lang>/` must have the same names as those in `doc/en/`.
- Hungarian strings run longer. Leave room in layouts and test both languages.
- The Discord showcase displays real bot responses. The bot's texts are owned by `shared/localization/responses/{lang}.l10n.json`; never copy them into the website files. A showcase message points at one by **exact key** and `resolveMessages` (`_lib/functions/botLocale.ts`) renders the whole payload (content, embeds, Components V2):

  ```json
  { "username": "fm01", "avatar": "/images/logo.webp", "bot": true,
    "botResponse": "work.embeds",
    "values": { "amount": { "randomInt": [50, 500] }, "random": { "botList": "work.random" } } }
  ```

  - A key missing in the page's language falls back to English (e.g. `giveaway.layout.active` has no Hungarian text yet).
  - Placeholders are filled from the closest preceding user command (`?!warn @rnxm 1w Hacking threats` fills `warn.user.mention`, `warn.length`, `warn.reason`), then from `values`, which win.
  - A value is a string, `{ "botText": key }`, `{ "botList": key }` (random entry; its own placeholders are filled too), or `{ "randomInt": [min, max], "prefix"?: "#" }`.
  - Renaming a bot key breaks the showcase (only a `console.warn` at render time). `pnpm check:l10n` and CI catch it: a key missing in English is an error, missing only in Hungarian is a warning.

## 5. Conventions

- Server components by default. Add `'use client'` only where state, effects or browser APIs are needed.
- Reuse the `@utility` classes in `globals.css` (`primary-button`, `accent-button`, `btn-sec`, `link`, `navbar`, `footer`, `tier-cards`, …) instead of re-creating them with ad-hoc classes.
- Colour only through the Tailwind theme aliases (`bg-primary`, `text-text/50`, `bg-contrast`, …). Never use a raw hex in a component.
- Responsive styles use the custom `laptop:` variant (54rem). Don't introduce other breakpoints.
- `SITE_URL` in `_lib/functions/metadata.ts` is the canonical origin for metadata and OG images.
- Pre-commit (`prek.toml`, repo root) reformats JSON with `--no-ensure-ascii`, so Hungarian characters stay literal.

---

## 6. Design system

Source: the **fm01** design system, https://claude.ai/artifact/9Xu1qJQfcdx2saFQVJRpYz (synced from `fm01-bot/website@124907a`, 2026-11-10). It's the reference for visual decisions. Where it and `globals.css` disagree, the code wins; update the design system afterwards.

### Voice and copy

- Address the server owner as **you**. fm01 speaks as itself or as "we".
- Headlines are short and lightly playful ("Your all-in-one bot", "Trusted by communities"). Feature descriptions are one line ending in "!".
- Buttons are 2–3 words in sentence case: "Try it now", "Get started for free", "Add to Server".
- Always write **fm01** in lowercase, never "FM01" or "Fm01".
- **No emoji in site copy, headings or UI.** Emoji appear only inside mock Discord messages ("React with 🎉 to enter!").
- Wherever Discord's look is borrowed, the footer must say "Not affiliated with Discord Inc."

### Colour

| Token (`--theme-*` / Tailwind)  | Light     | Dark      | Use                                                                                        |
| ------------------------------- | --------- | --------- | ------------------------------------------------------------------------------------------ |
| `bg` / `background`             | `#e2e3e4` | `#1b1c1d` | Page background                                                                            |
| `text` / `text`                 | `#030507` | `#f8fafc` | Body text and icons; tinted for muted text, hairlines and glass                            |
| `primary` / `primary`           | `#245fd0` | `#6094eb` | Logo, wordmark, primary buttons, links, the highlighted hero word, the Premium tier        |
| `secondary` / `secondary`       | `#3865b2` | `#3865b2` | Deeper blue (same in both themes); small labels on blue fills (5.7:1 with white)           |
| `accent` / `accent`             | `#bf3fd9` | `#da47f8` | **Only** the invite CTA, the last nav link (Premium), the Custom tier and its glow          |
| `contrast` / `contrast`         | `#cdcdd4` | `#0e0e0f` | Cards; at 30% under a blur it's the glass of the nav pill and footer                       |
| `available`                     | `#0bdb00` | `#078c00` | Status up                                                                                  |
| `interrupted`                   | `#ffb650` | `#ff9500` | Status degraded                                                                            |
| `unavailable`                   | `#ff5050` | `#8c0000` | Status down                                                                                |

- Text on primary, secondary and accent fills is `white`.
- **No new greys.** Tint `text` instead:
  - `/3`: hero grid lines and the showcase feed.
  - `/5`: fills.
  - `/10`: borders and glass buttons.
  - `/20`: hover states and the nav pill border.
  - `/50` and `/55`: secondary text.
- Status colours are for status only, and always sit beside a word ("Operational"), never colour alone.
- **Contrast caveats.** These are the brand's own values and are kept as they are:
  - Light `primary` as text is 2.5:1 on `bg`. Use it as text only at 24px+ or bold display sizes.
  - White on `primary` is 3.3:1 (3.0:1 in dark). Primary buttons need extrabold (800) text at 18px+. For a smaller label on blue, use `secondary`.
  - White on `accent` is 4.3:1 in light and 3.4:1 in dark. It reads at 18px+ extrabold.

### Type

- **Inter only**: the bundled variable `Inter-FM01` (`public/fonts/Inter.ttf`, weights 100–900).
- Flag emoji use a flags-only subset (`public/fonts/NotoColorEmoji-flags.woff2`, family `Emoji`) through `.emoji`.
- Sizes are fluid `clamp()` pairs. The values below are min → max.

| Style         | Size                                     | Weight | Notes                                                                 |
| ------------- | ---------------------------------------- | ------ | --------------------------------------------------------------------- |
| Hero          | clamp(3rem, 10vw, 6rem), line-height 0.85 | 800    | The middle word in `primary`                                          |
| Section title | clamp(1.875rem, 5vw, 3.75rem)            | 700    | Centred                                                               |
| Subtext       | clamp(1rem, 3vw, 1.875rem)               | 400    | 50% opacity                                                           |
| Hero subline  | clamp(1.125rem, 3vw, 1.5rem)             | 500    | `text/55`                                                             |
| Tier title    | clamp(1.5rem, 4vw, 2rem)                 | 900    |                                                                       |
| Tier price    | 1.2rem                                   | 700    |                                                                       |
| Wordmark      | 1.875rem                                 | 900    | `primary`                                                             |
| Button / lg   | 1rem / 1.25rem                           | 800    |                                                                       |
| Body          | 1rem / 1.5                               | 400    |                                                                       |
| Small         | 0.875rem                                 | 400    | Footer headings in uppercase                                          |

- **Every heading is centred.** Secondary lines drop opacity, not weight.
- `/features` has its own display scale (`_lib/css/features.css`, all on theme tokens, works in both themes):

| Style            | Size                                         | Weight | Notes                                                    |
| ---------------- | -------------------------------------------- | ------ | -------------------------------------------------------- |
| Features hero    | clamp(3rem, 8vw, 6rem), line-height 0.9      | 800    | Tracking -0.03em; highlighted words in `primary`         |
| Features heading | clamp(1.875rem, 5vw, 3.5rem), line-height 1.02 | 700  | Tracking -0.02em                                         |
| Features lead    | clamp(1rem, 1.6vw, 1.25rem), line-height 1.625 | 400  | `text/60`                                                |
| Kicker           | 0.875rem                                     | 700    | Uppercase, tracking 0.08em, numbered `primary`/`accent` badge |
| Chip             | 0.875rem                                     | 400    | On `text/10`, `rounded-lg`                               |

- Demo panels: `contrast` cards, `rounded-2xl`, 1px `text/5` border (4px `accent` border on the branding panel). Grid cards: `p-6`, `rounded-2xl`, lift on hover, icon tile `rounded-xl` at `primary/15`.

### Layout, shape and surfaces

- **Breakpoint and width:** one breakpoint, `laptop` (54rem / 864px). Content is capped at 70rem (`w-280`).
- **Radius:**
  - Buttons are `rounded-lg` on mobile and `rounded-2xl` on laptop.
  - Cards, the nav pill and the footer are `rounded-2xl`.
  - Buttons inside mock Discord messages are `rounded-sm`.
  - Pills and the burger bars are `rounded-full`.
- **Padding:** mobile buttons use `py-2 px-4` (accent `px-3`). Laptop buttons grow to `py-3`/`py-4` with `px-6`/`px-8`.
- **Shadows:** none, except the 20px `accent` glow on accent-button hover and the 4px `primary` drop-shadow on nav-link hover.
- **Glass:** `contrast` at 30% under a heavy backdrop blur.
  - The nav pill uses a 24px blur and a 2px `text/20` border.
  - The footer uses a 40px blur, a 1px `text/5` border and a soft shadow.
  - The mobile menu is a full-screen overlay of `background` at 95%.
- **Hero background:** a faint 121px grid of `text` lines at 3%, fading toward the bottom.

### Motion

- Everything transitions `all` over 200ms. A global rule in `globals.css` does this.
- The primary button scales to 110% on hover.
- The promoted-servers strip loops every 15s, with alternate rows reversed and edges faded 8%.
- The theme-switch ring slides in 300ms.
- Use Framer Motion for section entrances only.

### Components

| Component         | Where in code                                         | Rules                                                                                                                                                                     |
| ----------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AccentButton`    | `@utility accent-button`, `main/Hero.tsx`             | The invite CTA with `faDiscord` on the left. **Once per view.** Glow on hover.                                                                                            |
| `PrimaryButton`   | `@utility primary-button`                             | Solid `primary`; closes a section ("Get started for free"). Scales 110% on hover. Not for small labels.                                                                    |
| `SecondaryButton` | `@utility btn-sec`                                    | Glass `text/10` (`/20` on hover). Sits on `bg`, never on a coloured fill.                                                                                                 |
| `TextLink`        | `@utility link`                                       | `primary` text, underlined on hover.                                                                                                                                      |
| `TierCard`        | `@utility tier-cards`, `main/Premium.tsx`             | `contrast` card, `rounded-2xl`, 20.5×22.5rem on laptop, 4px border (Premium only). Free has an inverted button; Premium is `primary`; Custom is `accent`. Features use `faCircleCheck`. |
| `Navbar`          | `@utility navbar`, `Header.tsx`                       | Logo and wordmark, a glass link pill (the last link, Premium, is `accent`), then theme, `LangSelector` and the `primary` Dashboard button. Below `laptop` it becomes a burger with a full-screen overlay. |
| `Footer`          | `@utility footer`, `Footer.tsx`                       | Glass card: contact, three link columns, then status (a pinging `available` dot beside the words "System status"), copyright and the theme switch.                        |
| `FeatureShowcase` | `showcase-container`, `main/showcase/*`               | A Discord-style channel list and feed. The APP badge uses Discord blurple `#5865f2`, the only allowed non-token colour. Embeds have a 6px left border. On mobile the channel list becomes a drawer. |
| `ServerCard`      | `main/PromotedServers.tsx`                            | `contrast` card with a 60px icon, the name in 24px semibold and the count beside the Members glyph. The last card is an "Your Server · Invite now" slot.                   |

- For the hero pair, put **one accent button and one secondary button** side by side. Never put two filled buttons together.
- An action that isn't available yet uses the **Unavailable** state: greyed out at 50% opacity, no glow, `cursor-not-allowed`.
- Keep the Discord look inside the showcase. Don't reuse it elsewhere.

### Iconography and logo

- Font Awesome 7 (solid, regular, brands) for UI glyphs. Icons inherit the text colour.
  - `faDiscord` on invite buttons.
  - `faCircleCheck` for plan features.
  - `faSun`, `faMoon` and `faDesktop` for the theme switch.
- Custom glyphs: `_lib/svg/Dashboard.tsx` and `_lib/svg/Members.tsx`.
- The fm01 mark (`_lib/svg/Logo.tsx`) is `primary` on light grounds and `white` on dark grounds or primary fills. Never redraw, stretch or recolour it outside the palette.
- The app icon is the bot's avatar wherever fm01 "speaks", as in the showcase.

### Known gaps

- `_lib/css/t.css`, `t.html` and `t.js` are drafts of `/features`. They hard-code white tints (`rgba(255,255,255,…)`), so they work only in dark, and they aren't part of the design system. Don't copy from them; use theme tokens.
- The design system was re-synced for `/features`, the emoji font and source paths at `90ca1e4` (2026-11-19); other components still date from `124907a`. If its notes and the code disagree, trust the code.
- `/features` uses `accent-button` twice (hero CTA and the branding panel CTA), which breaks the design system's AccentButton rule (once per view). Decide which one stays accent.
