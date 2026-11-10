import { NextRequest, NextResponse } from "next/server";

export function proxy(request: NextRequest) {
    const locales = ['en', 'hu'] as const;
    const defaultLocale = 'en';

    const { pathname } = request.nextUrl;
    const pathnameHasLocale = locales.some(
        (locale) => pathname.startsWith(`/${locale}/`) || pathname === `/${locale}`
    );

    if (pathnameHasLocale) return NextResponse.next();

    const savedLocale = request.cookies.get('locale')?.value;
    const locale = locales.includes(savedLocale as typeof locales[number])
        ? savedLocale
        : defaultLocale;
    const rewrittenUrl = request.nextUrl.clone();
    rewrittenUrl.pathname = `/${locale}${pathname}`;

    return NextResponse.rewrite(rewrittenUrl);
}

export const config = {
    matcher: [
        '/((?!api|_next/static|_next/image|favicon.ico|favicons|images|fonts|api).*)',
    ],
}