import { notFound } from "next/navigation";
import Link from "next/link";
import fs from "fs/promises";
import path from "path";
import { MDXRemote } from "next-mdx-remote/rsc";
import { hasLocale } from "../../dictionaries";

// Optional: Pass custom or client components here if your MDX uses them
const components = {
    // Add any custom components used inside your MDX files here
    // Example: MyComponent,
};

type LegalDoc = {
    title: string;
    mdx: string;
};

const LEGAL_DATA: Record<string, LegalDoc> = {
    providers: { title: "Providers", mdx: "documents/providers.mdx" },
    "bot/tos": { title: "Bot - Terms of Service", mdx: "documents/bot-tos.mdx" },
    "bot/privacy": { title: "Bot - Privacy Policy", mdx: "documents/bot-privacy.mdx" },
    "web/tos": { title: "Website - Terms of Service", mdx: "documents/web-tos.mdx" },
    "web/privacy": { title: "Website - Privacy Policy", mdx: "documents/web-privacy.mdx" },
    "web/cookies": { title: "Website - Cookie Policy", mdx: "documents/web-cookies.mdx" },
};

const NAV_GROUPS = [
    {
        label: "LEGAL",
        items: [{ path: "providers", title: "Providers" }],
    },
    {
        label: "Discord bot",
        items: [
            { path: "bot/tos", title: "Terms of Service" },
            { path: "bot/privacy", title: "Privacy Policy" },
        ],
    },
    {
        label: "Website",
        items: [
            { path: "web/tos", title: "Terms of Service" },
            { path: "web/privacy", title: "Privacy Policy" },
            { path: "web/cookies", title: "Cookie Policy" },
        ],
    },
];

export default async function Page({
    params,
}: {
    params: Promise<{ lang: string; doc?: string[] }>;
}) {
    const { lang, doc } = await params;

    if (!hasLocale(lang)) {
        notFound();
    }

    if (!doc?.length) {
        return <h1>Legal Documents Directory</h1>;
    }

    const data = LEGAL_DATA[doc.join("/")];
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

    return (
        <div className="legal">
            <div className="hero">
                <h1>{data.title}</h1>
            </div>
            <div className="legal-container flex">
                <aside className="legal-sidebar w-64 pr-8">
                    {NAV_GROUPS.map((group) => (
                        <div key={group.label} className="mb-6">
                            <h3 className="font-bold uppercase mb-2 text-sm">{group.label}</h3>
                            <ul className="legal-links space-y-2">
                                {group.items.map((item) => (
                                    <li key={item.path}>
                                        <Link
                                            href={`/${lang}/legal/${item.path}`}
                                            className={`block ${item.path === doc.join("/") ? "font-bold" : "opacity-70 hover:opacity-100"}`}
                                        >
                                            {item.title}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </aside>
                <div className="doc flex-1">
                    <MDXRemote source={mdxContent} options={options} components={components} />
                </div>
            </div>
        </div>
    );
}
