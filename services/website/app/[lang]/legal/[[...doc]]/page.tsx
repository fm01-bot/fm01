import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "fs/promises";
import path from "path";
import { MDXRemote } from "next-mdx-remote/rsc";
import { getDictionary, hasLocale } from "../../dictionaries";
import type { Metadata } from "next";
import { pageMetadata } from "@/_lib/functions/metadata";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faArrowRight } from "@fortawesome/free-solid-svg-icons";
import "@lib/css/legal.css";

type Dictionary = Awaited<ReturnType<typeof getDictionary>>;
type LegalLang = Dictionary["legal"];
type DocKey = keyof LegalLang["documents"];

/** URL path → MDX file and its key in the `legal.documents` dictionary. */
const LEGAL_DATA: Record<string, { key: DocKey; mdx: string }> = {
    providers: { key: "providers", mdx: "documents/providers.mdx" },
    "bot/tos": { key: "bot-tos", mdx: "documents/bot-tos.mdx" },
    "bot/privacy": { key: "bot-privacy", mdx: "documents/bot-privacy.mdx" },
    "web/tos": { key: "web-tos", mdx: "documents/web-tos.mdx" },
    "web/privacy": { key: "web-privacy", mdx: "documents/web-privacy.mdx" },
    "web/cookies": { key: "web-cookies", mdx: "documents/web-cookies.mdx" },
};

/** `label` is a key in `legal.groups`; a group without one has no heading. */
const NAV_GROUPS: { label?: keyof LegalLang["groups"]; items: string[] }[] = [
    { items: ["providers"] },
    { label: "bot", items: ["bot/tos", "bot/privacy"] },
    { label: "web", items: ["web/tos", "web/privacy", "web/cookies"] },
];

type PageProps = {
    params: Promise<{ lang: string; doc?: string[] }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { lang, doc } = await params;
    const current = doc?.join("/") ?? "";
    if (!hasLocale(lang)) return {};

    const t = (await getDictionary(lang)).legal;

    if (!current) {
        return pageMetadata({
            lang,
            path: "/legal",
            title: t.index.meta_title,
            description: t.index.meta_description,
        });
    }

    const data = LEGAL_DATA[current];
    if (!data) return {};

    const title = t.documents[data.key].title;
    return pageMetadata({
        lang,
        path: `/legal/${current}`,
        title,
        description: t.meta_description.replace("{title}", title),
    });
}

export default async function Page({ params }: PageProps) {
    const { lang, doc } = await params;

    if (!hasLocale(lang)) {
        notFound();
    }

    const t = (await getDictionary(lang)).legal;

    // The bare /legal route lists every document.
    if (!doc?.length) {
        return <LegalIndex t={t} />;
    }

    const current = doc.join("/");
    const data = LEGAL_DATA[current];
    if (!data) {
        notFound();
    }

    const filePath = path.join(process.cwd(), "_lib", "translations", lang, data.mdx);
    let mdxContent: string;

    try {
        mdxContent = await fs.readFile(filePath, "utf8");
    } catch {
        console.error(`Failed to read MDX file at ${filePath}`);
        notFound();
    }

    const options = {
        mdxOptions: {
            remarkPlugins: [],
            rehypePlugins: [],
            format: "mdx" as const,
        },
        parseFrontmatter: true,
        scope: {
            currentYear: new Date().getFullYear(),
        },
        blockJS: false,
    };

    const title = t.documents[data.key].title;

    // The last word of the title is highlighted in the header.
    const titleWords = title.split(" ");
    const titleLast = titleWords.pop();

    return (
        <div className="legal-page">
            <section className="legal-hero">
                <div className="legal-hero-backdrop is-grid" aria-hidden="true" />
                <div className="legal-hero-inner">
                    <nav aria-label={t.breadcrumb_label} className="legal-breadcrumb">
                        <Link href="/legal">{t.breadcrumb}</Link>
                        <span aria-hidden="true">/</span>
                        <span>{title}</span>
                    </nav>
                    <h1 className="legal-title">
                        {titleWords.length ? `${titleWords.join(" ")} ` : ""}
                        <span>{titleLast}</span>
                    </h1>
                </div>
            </section>

            <div className="legal-layout">
                <aside aria-label={t.nav_label} className="legal-nav">
                    {NAV_GROUPS.map((group, i) => (
                        <div key={group.label ?? i} className="legal-nav-group">
                            <div className="legal-nav-label">
                                {group.label ? t.groups[group.label] : null}
                            </div>
                            {group.items.map((item) => {
                                const active = item === current;
                                return (
                                    <Link
                                        key={item}
                                        href={`/legal/${item}`}
                                        aria-current={active ? "page" : undefined}
                                        className="legal-nav-link"
                                    >
                                        {t.documents[LEGAL_DATA[item].key].nav}
                                    </Link>
                                );
                            })}
                        </div>
                    ))}
                </aside>
                <article className="legal-doc legal-article">
                    <MDXRemote source={mdxContent} options={options} />
                </article>
            </div>
        </div>
    );
}

function LegalIndex({ t }: { t: LegalLang }) {
    return (
        <div className="legal-page">
            <section className="legal-hero">
                <div className="legal-hero-backdrop" aria-hidden="true" />
                <div className="legal-hero-inner is-centered">
                    <h1 className="legal-index-title">
                        {t.index.title[0]} <span>{t.index.title[1]}</span>
                    </h1>
                    <p className="legal-index-subtext">{t.index.subtext}</p>
                </div>
            </section>

            <div className="legal-groups">
                {NAV_GROUPS.map((group, i) => {
                    const headingId = `legal-group-${i}`;
                    return (
                        <section key={group.label ?? i} aria-labelledby={group.label ? headingId : undefined}>
                            {group.label ? (
                                <h2 id={headingId} className="legal-group-title">
                                    {t.groups[group.label]}
                                </h2>
                            ) : null}
                            <ul className="legal-cards">
                                {group.items.map((item) => {
                                    const docLang = t.documents[LEGAL_DATA[item].key];
                                    return (
                                        <li key={item}>
                                            <Link href={`/legal/${item}`} className="legal-card">
                                                <span className="legal-card-title">
                                                    {docLang.nav}
                                                    <FontAwesomeIcon icon={faArrowRight} className="legal-card-arrow" aria-hidden="true" />
                                                </span>
                                                <span className="legal-card-description">{docLang.description}</span>
                                            </Link>
                                        </li>
                                    );
                                })}
                            </ul>
                        </section>
                    );
                })}
            </div>
        </div>
    );
}
