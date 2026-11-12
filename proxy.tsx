import { NextRequest, NextResponse } from "next/server";
import Negotiator from "negotiator";
import { match } from "@formatjs/intl-localematcher";

const locales = ['en', 'hu'] as const;
const defaultLocale = 'en';
const COOKIE = 'locale';

type Locale = typeof locales[number];
const isLocale = (v: string | undefined): v is Locale => locales.includes(v as Locale);

/**
 * Locale routing without a locale in the URL.
 *
 * Public URLs are bare (`/`, `/features`, ...). The locale comes from the
 * `locale` cookie, falling back to the Accept-Language header, and the request
 * is rewritten internally to the matching `app/[lang]/...` route. Legacy
 * prefixed URLs (`/hu/features`) redirect to the bare path and set the cookie,
 * so old links keep working and land in the right language.
 *
 * `x-locale` is set on the forwarded request so app/layout.tsx (<html lang>)
 * and app/not-found.tsx, which sit outside the [lang] segment, know the locale.
 */
export function proxy(request: NextRequest) {
    const { pathname, search } = request.nextUrl;

    const prefixed = locales.find(
        (locale) => pathname === `/${locale}` || pathname.startsWith(`/${locale}/`)
    );
    if (prefixed) {
        const url = request.nextUrl.clone();
        url.pathname = pathname.slice(prefixed.length + 1) || '/';
        url.search = search;
        const response = NextResponse.redirect(url, 307);
        setLocaleCookie(response, prefixed);
        return response;
    }

    const saved = request.cookies.get(COOKIE)?.value;
    const locale = isLocale(saved) ? saved : negotiateLocale(request);

    const headers = new Headers(request.headers);
    headers.set('x-locale', locale);

    const rewrittenUrl = request.nextUrl.clone();
    rewrittenUrl.pathname = `/${locale}${pathname === '/' ? '' : pathname}`;

    return NextResponse.rewrite(rewrittenUrl, { request: { headers } });
}

function negotiateLocale(request: NextRequest): Locale {
    const acceptLanguage = request.headers.get('accept-language');
    if (!acceptLanguage) return defaultLocale;
    try {
        const wanted = new Negotiator({ headers: { 'accept-language': acceptLanguage } }).languages();
        return match(wanted, locales, defaultLocale) as Locale;
    } catch {
        return defaultLocale;
    }
}

function setLocaleCookie(response: NextResponse, locale: Locale) {
    response.cookies.set(COOKIE, locale, {
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge: 60 * 60 * 24 * 365,
    });
}

export const config = {
    matcher: [
        '/((?!api|_next/static|_next/image|favicon.ico|favicons|images|fonts).*)',
    ],
}
