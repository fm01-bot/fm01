import Header from '@/_lib/components/Header';
import Footer from '@/_lib/components/Footer';
import HtmlLang from '@/_lib/components/HtmlLang';
import { notFound } from 'next/navigation';
import { getDictionary, hasLocale } from './dictionaries';
import type { Metadata } from 'next';
import { SITE_NAME, SITE_URL } from '@/_lib/functions/metadata';

type LayoutProps = {
    children: React.ReactNode;
    params: Promise<{ lang: string }>;
};

export const metadata: Metadata = {
    metadataBase: new URL(SITE_URL),
    title: { default: SITE_NAME, template: `%s | ${SITE_NAME}` },
    description: 'fm01bot, utility for your server.',
    applicationName: SITE_NAME,
    openGraph: {
        type: 'website',
        url: '/',
        siteName: SITE_NAME,
        title: SITE_NAME,
        description: 'fm01bot, utility for your server.',
        images: [{ url: '/api/og', width: 1200, height: 630, alt: SITE_NAME }],
    },
    twitter: {
        card: 'summary_large_image',
        images: ['/api/og'],
    },
    other: {
        'twitter:url': SITE_URL,
    },
    icons: {
        icon: [
            { url: '/favicons/favicon-32x32.png', sizes: '32x32', type: 'image/png' },
            { url: '/favicons/favicon-16x16.png', sizes: '16x16', type: 'image/png' },
        ],
        apple: [
            { url: '/favicons/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
        ],
    },
    manifest: '/favicons/site.webmanifest',
};

export default async function Layout({
    children,
    params
}: LayoutProps) {
    const { lang } = await params;

    if (!hasLocale(lang)) notFound();

    const dict = await getDictionary(lang);

    return (
        <>
            {/* og:logo isn't in Next's metadata API; React hoists this tag into <head>. */}
            <meta property="og:logo" content={`${SITE_URL}/images/logo.png`} />
            <HtmlLang lang={lang} />
            <Header lang={dict.header} code={lang} />
            <main>
                <div className="w-full flex items-center justify-center max-w-screen">
                    <div className="w-280 max-w-screen">
                        <div className="absolute w-screen h-screen top-0 left-0 grid-bg -z-1">
                        </div>
                        <div className='px-2 laptop:px-6'>
                            {children}
                        </div>
                    </div>
                </div>
            </main>
            <Footer lang={dict.footer} />
        </>
    );
}
