import type { Metadata } from 'next';

export const SITE_URL = 'https://fm01.bot';
export const SITE_NAME = 'fm01bot';

const OG_LOCALES: Record<string, string> = {
    en: 'en_US',
    hu: 'hu_HU',
};

type PageMetadataInput = {
    lang: string;
    /** Page path, e.g. "" for the home page or "/features". */
    path: string;
    title: string;
    description: string;
    /** Title drawn on the generated preview image. Defaults to `title`. */
    imageTitle?: string;
};

/**
 * Builds title, description, canonical link, Open Graph and Twitter card tags
 * for a page. The locale is not part of the URL (it comes from the cookie), so
 * canonical is the bare path and there are no per-language alternates. Relative URLs resolve against `metadataBase` set in the
 * root layout.
 */
export function pageMetadata({ lang, path, title: pageTitle, description, imageTitle }: PageMetadataInput): Metadata {
    const url = path || '/';
    // Same full title everywhere (<title>, og:title, twitter:title) so link
    // previews get a descriptive title, not just "Features".
    const title = `${pageTitle} | ${SITE_NAME}`;
    const image = {
        url: `/api/og?${new URLSearchParams({ title: imageTitle ?? pageTitle, description })}`,
        width: 1200,
        height: 630,
        alt: title,
    };

    return {
        title: { absolute: title },
        description,
        alternates: {
            canonical: url,
        },
        openGraph: {
            type: 'website',
            siteName: SITE_NAME,
            url,
            title,
            description,
            locale: OG_LOCALES[lang] ?? 'en_US',
            images: [image],
        },
        twitter: {
            card: 'summary_large_image',
            title,
            description,
            images: [image.url],
        },
        // Next's twitter metadata has no url field; `other` needs an absolute URL.
        other: {
            'twitter:url': `${SITE_URL}${url}`,
        },
    };
}
