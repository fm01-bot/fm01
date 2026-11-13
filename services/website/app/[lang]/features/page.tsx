import { notFound } from 'next/navigation';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import type { IconDefinition } from '@fortawesome/fontawesome-svg-core';
import {
    faChartLine,
    faCircleInfo,
    faClockRotateLeft,
    faCoins,
    faGift,
    faGlobe,
    faMessage,
    faRightToBracket,
} from '@fortawesome/free-solid-svg-icons';
import { getDictionary, hasLocale } from '../dictionaries';
import Message from '@/_lib/components/main/showcase/Message';
import AddNow from '@/_lib/components/main/AddNow';
import { MessageType } from '@/_lib/types/MessageLang';
import '@lib/css/features.css';
import type { Metadata } from 'next';
import { pageMetadata } from '@/_lib/functions/metadata';
import { resolveMessages } from '@/_lib/functions/botLocale';

type PageProps = {
    params: Promise<{ lang: string }>;
};

/* ---------- Data ---------- */

type Dictionary = Awaited<ReturnType<typeof getDictionary>>;
type FeaturesLang = Dictionary['features'];

const MORE_ICONS: Record<keyof FeaturesLang['more']['items'], IconDefinition> = {
    economy: faCoins,
    giveaways: faGift,
    levels: faChartLine,
    information: faCircleInfo,
    localization: faGlobe,
    custom_messages: faMessage,
    join_leave: faRightToBracket,
    snapshots: faClockRotateLeft,
};


/* ---------- Building blocks ---------- */

function DiscordPanel({
    channel,
    description,
    branded,
    children,
}: {
    channel: string;
    description?: string;
    branded?: boolean;
    children: ReactNode;
}) {
    return (
        <div className={`discord-panel discord-chat ${branded ? 'is-branded' : ''}`}>
            <div className="discord-panel-head">
                <span>#</span>
                {channel}
                {description ? <span>· {description}</span> : null}
            </div>
            {children}
        </div>
    );
}

function FeatureCopy({
    number,
    kicker,
    title,
    highlight,
    text,
    chips,
}: {
    number: string;
    kicker: string;
    title: string;
    highlight: string;
    text: string;
    chips: string[];
}) {
    return (
        <div className="feature-copy">
            <div className="kicker">
                <b>{number}</b>
                {kicker}
            </div>
            <h2>
                {title}
                <br />
                <span>{highlight}</span>
            </h2>
            <p className="lead">{text}</p>
            <div className="chips">
                {chips.map((chip) => (
                    <span key={chip}>{chip}</span>
                ))}
            </div>
        </div>
    );
}

/* ---------- Page ---------- */

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
    const { lang } = await params;
    if (!hasLocale(lang)) return {};

    const meta = (await getDictionary(lang)).features.meta;
    return pageMetadata({
        lang,
        path: '/features',
        title: meta.title,
        description: meta.description,
        imageTitle: meta.image_title,
    });
}

export default async function Page({ params }: PageProps) {
    const { lang } = await params;
    if (!hasLocale(lang)) notFound();

    const dict = await getDictionary(lang);
    const t = dict.features;

    /** A section's mock Discord messages, with `bot-locale.*` embed references resolved. */
    const messagesOf = (section: { messages: unknown }) =>
        resolveMessages(dict, section.messages as MessageType[]);

    return (
        <div className="features-page">
            <section className="features-hero" aria-label={t.hero.aria}>
                <h1>
                    {t.hero.title[0]}
                    <br />
                    <span>{t.hero.title[1]}</span> {t.hero.title[2]}
                </h1>
                <p>{t.hero.subtext}</p>
                <div className="features-hero-buttons">
                    <Link href="https://add.fm01.bot">{dict.main.hero.invite_btn}</Link>
                    <Link href="/#premium">{t.hero.pricing}</Link>
                </div>
            </section>

            <section className="feature-row" id="moderation">
                <FeatureCopy number="01" {...t.moderation} />
                <DiscordPanel channel={t.moderation.channel} description={t.moderation.channel_description}>
                    <div className="discord-panel-body">
                        {messagesOf(t.moderation).map((m, i) => (
                            <Message key={i} {...m} />
                        ))}
                    </div>
                </DiscordPanel>
            </section>

            <section className="feature-row reverse" id="security">
                <FeatureCopy number="02" {...t.security} />
                <DiscordPanel channel={t.security.channel} description={t.security.channel_description}>
                    <div className="discord-panel-body">
                        {messagesOf(t.security).map((m, i) => (
                            <Message key={i} {...m} />
                        ))}
                    </div>
                </DiscordPanel>
            </section>

            <section className="feature-row" id="music">
                <FeatureCopy number="03" {...t.music} />
                <DiscordPanel channel={t.music.channel} description={t.music.channel_description}>
                    <div className="discord-panel-body">
                        {messagesOf(t.music).map((m, i) => (
                            <Message key={i} {...m} />
                        ))}
                    </div>
                </DiscordPanel>
            </section>

            <section className="feature-row reverse" id="logging">
                <FeatureCopy number="04" {...t.logging} />
                <DiscordPanel channel={t.logging.channel} description={t.logging.channel_description}>
                    <div className="discord-feed">
                        {/* Newest first: the feed is flex-col-reverse, so the first entry sits at the bottom. */}
                        {messagesOf(t.logging).map((m, i) => (
                            <Message key={i} {...m} />
                        ))}
                    </div>
                </DiscordPanel>
            </section>

            <section className="features-more" id="more">
                <div className="kicker">{t.more.kicker}</div>
                <h2>{t.more.title}</h2>
                <p className="lead">{t.more.text}</p>
                <div className="features-grid">
                    {(Object.keys(MORE_ICONS) as (keyof typeof MORE_ICONS)[]).map((key) => (
                        <article key={key}>
                            <span className="features-grid-icon">
                                <FontAwesomeIcon icon={MORE_ICONS[key]} />
                            </span>
                            <b>{t.more.items[key].title}</b>
                            <p>{t.more.items[key].text}</p>
                        </article>
                    ))}
                </div>
            </section>

            <section className="feature-row" id="branding">
                <div className="feature-copy">
                    <div className="kicker is-accent">
                        <b>✦</b>
                        {t.branding.kicker}
                    </div>
                    <h2>
                        {t.branding.title}
                        <br />
                        <span className="is-accent">{t.branding.highlight}</span>
                    </h2>
                    <p className="lead">{t.branding.text}</p>
                    <Link href="/#premium" className="feature-cta">
                        {t.branding.cta}
                    </Link>
                </div>
                <DiscordPanel channel={t.branding.channel} branded>
                    <div className="discord-panel-body">
                        {messagesOf(t.branding).map((m, i) => (
                            <Message key={i} {...m} />
                        ))}
                    </div>
                </DiscordPanel>
            </section>

            <AddNow lang={dict.main.invite} />
        </div>
    );
}
