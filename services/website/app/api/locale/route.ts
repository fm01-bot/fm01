import { NextResponse } from "next/server";

const supportedLocales = ["en", "hu"] as const;
const defaultLocale = "en";

export async function POST(request: Request) {
    let body: { locale?: unknown };

    try {
        body = await request.json() as { locale?: unknown };
    } catch {
        return NextResponse.json({ error: "Invalid request body." }, { status: 400 });
    }

    const locale = typeof body.locale === "string" && supportedLocales.includes(body.locale as typeof supportedLocales[number])
        ? body.locale
        : defaultLocale;

    const response = NextResponse.json({ locale });
    response.cookies.set("locale", locale, {
        httpOnly: true,
        sameSite: "lax",
        secure: process.env.NODE_ENV === "production",
        path: "/",
        maxAge: 60 * 60 * 24 * 365,
    });

    return response;
}
