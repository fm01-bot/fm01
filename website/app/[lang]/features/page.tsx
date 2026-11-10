'use client';

import { useEffect } from 'react';

const styles = `
    .fm01-features {
        --f-border: rgba(255, 255, 255, 0.09);
        --f-muted: rgba(255, 255, 255, 0.58);
        --f-card: rgba(255, 255, 255, 0.035);
        max-width: 1180px;
        margin: auto;
        padding: 0 24px 100px;
    }

    .fm01-features-hero {
        padding: 105px 0 65px;
        text-align: center;
    }

    .fm01-kicker,
    .fm01-copy > small,
    .fm01-more > small,
    .fm01-branding small {
        font-size: 10px;
        letter-spacing: 0.17em;
        font-weight: 800;
        opacity: 0.58;
    }

    .fm01-features-hero h1 {
        font-size: clamp(48px, 7vw, 88px);
        line-height: 0.96;
        letter-spacing: -0.06em;
        margin: 17px 0 22px;
    }

    .fm01-features-hero h1 span {
        opacity: 0.55;
    }

    .fm01-features-hero > p {
        max-width: 620px;
        margin: auto;
        color: var(--f-muted);
        line-height: 1.7;
        font-size: 16px;
    }

    .fm01-feature-tabs {
        position: sticky;
        top: 0;
        z-index: 4;
        display: flex;
        justify-content: center;
        gap: 7px;
        padding: 13px 0;
        margin-bottom: 15px;
        background: linear-gradient(to bottom, var(--site-background, transparent) 70%, transparent);
        backdrop-filter: blur(14px);
        overflow: auto;
    }

    .fm01-feature-tabs button {
        border: 1px solid var(--f-border);
        background: var(--f-card);
        color: inherit;
        opacity: 0.62;
        border-radius: 999px;
        padding: 9px 14px;
        font: 600 11px inherit;
        white-space: nowrap;
        cursor: pointer;
        transition: 0.2s;
    }

    .fm01-feature-tabs button:hover,
    .fm01-feature-tabs button.is-active {
        opacity: 1;
        background: rgba(255, 255, 255, 0.12);
        border-color: rgba(255, 255, 255, 0.2);
    }

    .fm01-feature-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        align-items: center;
        gap: 80px;
        padding: 125px 0;
        scroll-margin-top: 60px;
    }

    .fm01-feature-row.reverse .fm01-copy {
        order: 2;
    }

    .fm01-feature-row.reverse .fm01-demo {
        order: 1;
    }

    .fm01-copy h2,
    .fm01-more h2,
    .fm01-branding h2 {
        font-size: clamp(40px, 5vw, 67px);
        line-height: 0.98;
        letter-spacing: -0.055em;
        margin: 16px 0 24px;
    }

    .fm01-copy > p,
    .fm01-more > p,
    .fm01-branding p {
        max-width: 530px;
        color: var(--f-muted);
        font-size: 15px;
        line-height: 1.75;
    }

    .fm01-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        margin-top: 26px;
    }

    .fm01-chips span {
        font-size: 10px;
        font-weight: 650;
        border: 1px solid var(--f-border);
        padding: 7px 9px;
        border-radius: 7px;
        opacity: 0.68;
    }

    .fm01-demo {
        border: 1px solid var(--f-border);
        background: var(--f-card);
        border-radius: 17px;
        box-shadow: 0 25px 70px rgba(0, 0, 0, 0.16);
        overflow: hidden;
    }

    .discord-demo {
        padding: 18px;
    }

    .demo-channel {
        font-size: 11px;
        font-weight: 700;
        padding-bottom: 17px;
        border-bottom: 1px solid var(--f-border);
    }

    .demo-date {
        font-size: 8px;
        letter-spacing: 0.1em;
        opacity: 0.35;
        margin: 17px 0 4px;
    }

    .demo-msg {
        padding: 14px 0;
    }

    .demo-msg b {
        font-size: 11px;
    }

    .demo-msg i {
        font-style: normal;
        font-size: 8px;
        opacity: 0.35;
        margin-left: 7px;
    }

    .demo-msg p {
        font-size: 11px;
        opacity: 0.68;
        margin: 7px 0 0;
    }

    .demo-msg label {
        font-size: 7px;
        background: rgba(139, 124, 255, 0.35);
        border-radius: 3px;
        padding: 2px 4px;
        margin-left: 3px;
    }

    .demo-result {
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 13px;
        border: 1px solid rgba(139, 124, 255, 0.2);
        background: rgba(139, 124, 255, 0.07);
        border-radius: 9px;
    }

    .demo-result > strong {
        font-size: 16px;
    }

    .demo-result b {
        display: block;
        font-size: 10px;
    }

    .demo-result small {
        font-size: 8px;
        opacity: 0.45;
    }

    .demo-result em {
        margin-left: auto;
        font-style: normal;
        font-size: 7px;
        letter-spacing: 0.1em;
        opacity: 0.6;
    }

    .security-demo {
        padding: 19px;
    }

    .security-title {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 11px;
        padding-bottom: 16px;
        border-bottom: 1px solid var(--f-border);
    }

    .security-title span {
        font-size: 8px;
    }

    .security-title em {
        margin-left: auto;
        font-style: normal;
        font-size: 7px;
        letter-spacing: 0.12em;
        opacity: 0.5;
    }

    .security-rule {
        position: relative;
        padding: 16px 0;
        border-bottom: 1px solid var(--f-border);
    }

    .security-rule b {
        font-size: 10px;
    }

    .security-rule small {
        display: block;
        font-size: 8px;
        opacity: 0.4;
        margin-top: 4px;
    }

    .security-rule span {
        position: absolute;
        right: 0;
        top: 18px;
        font-size: 7px;
        font-weight: 800;
        opacity: 0.55;
    }

    .security-safe {
        display: flex;
        gap: 9px;
        margin-top: 16px;
        padding: 12px;
        border-radius: 8px;
        background: rgba(100, 220, 150, 0.06);
        font-size: 11px;
    }

    .security-safe small {
        display: block;
        font-size: 8px;
        opacity: 0.4;
        margin-top: 3px;
    }

    .music-demo {
        padding: 20px;
        text-align: center;
    }

    .album {
        height: 185px;
        border-radius: 11px;
        display: grid;
        place-items: center;
        font-size: 66px;
        background: radial-gradient(circle at 35% 25%, rgba(150, 135, 255, 0.55), rgba(255, 255, 255, 0.03) 65%);
    }

    .music-demo > small {
        display: block;
        font-size: 7px;
        letter-spacing: 0.16em;
        opacity: 0.4;
        margin-top: 20px;
    }

    .music-demo h3 {
        font-size: 15px;
        margin: 7px 0 3px;
    }

    .music-demo > p {
        font-size: 9px;
        opacity: 0.4;
        margin: 0;
    }

    .progress {
        height: 3px;
        border-radius: 3px;
        background: rgba(255, 255, 255, 0.09);
        margin-top: 22px;
    }

    .progress span {
        display: block;
        width: 43%;
        height: 100%;
        background: currentColor;
    }

    .times {
        display: flex;
        justify-content: space-between;
        font-size: 7px;
        opacity: 0.35;
        margin-top: 6px;
    }

    .player-controls {
        display: flex;
        justify-content: center;
        gap: 24px;
        align-items: center;
        margin: 20px;
    }

    .player-controls strong {
        font-size: 18px;
    }

    .player-controls b {
        font-size: 14px;
        opacity: 0.65;
    }

    .queue {
        display: flex;
        justify-content: space-between;
        border-top: 1px solid var(--f-border);
        padding-top: 14px;
        font-size: 8px;
        opacity: 0.55;
    }

    .log-demo {
        padding: 18px;
    }

    .log-head {
        display: flex;
        justify-content: space-between;
        font-size: 9px;
        padding-bottom: 14px;
        border-bottom: 1px solid var(--f-border);
    }

    .log-head span {
        font-size: 7px;
        letter-spacing: 0.1em;
        opacity: 0.5;
    }

    .log-demo > div:not(.log-head) {
        display: grid;
        grid-template-columns: 68px 1fr auto;
        gap: 10px;
        padding: 14px 0;
        border-bottom: 1px solid var(--f-border);
        align-items: center;
    }

    .log-demo time {
        font-size: 7px;
        opacity: 0.3;
    }

    .log-demo b {
        font-size: 9px;
    }

    .log-demo small {
        font-size: 8px;
        opacity: 0.4;
    }

    .fm01-more {
        padding: 125px 0;
        scroll-margin-top: 60px;
    }

    .fm01-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
        margin-top: 45px;
    }

    .fm01-grid article {
        border: 1px solid var(--f-border);
        background: var(--f-card);
        border-radius: 13px;
        padding: 21px;
        min-height: 155px;
        transition: 0.2s;
    }

    .fm01-grid article:hover {
        transform: translateY(-3px);
        background: rgba(255, 255, 255, 0.055);
    }

    .fm01-grid b {
        font-size: 12px;
    }

    .fm01-grid p {
        font-size: 10px;
        line-height: 1.65;
        opacity: 0.48;
        margin: 12px 0 0;
    }

    .fm01-branding {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 70px;
        align-items: center;
        padding: 125px 0 145px;
        scroll-margin-top: 60px;
    }

    .brand-preview {
        border: 1px solid var(--f-border);
        background: var(--f-card);
        border-radius: 16px;
        padding: 22px;
        display: flex;
        align-items: center;
        gap: 12px;
    }

    .brand-icon {
        width: 44px;
        height: 44px;
        border-radius: 11px;
        background: rgba(255, 255, 255, 0.9);
        color: #111;
        display: grid;
        place-items: center;
        font-weight: 850;
        font-size: 22px;
    }

    .brand-preview b {
        font-size: 12px;
    }

    .brand-preview small {
        display: block;
        font-size: 8px;
        opacity: 0.4;
        margin-top: 3px;
    }

    .brand-preview button {
        margin-left: auto;
        background: rgba(255, 255, 255, 0.9);
        color: #111;
        border: 0;
        border-radius: 7px;
        padding: 9px 11px;
        font: 700 9px inherit;
    }

    @media (max-width: 800px) {
        .fm01-feature-row,
        .fm01-branding {
            grid-template-columns: 1fr;
            gap: 45px;
            padding: 90px 0;
        }

        .fm01-feature-row.reverse .fm01-copy,
        .fm01-feature-row.reverse .fm01-demo {
            order: initial;
        }

        .fm01-grid {
            grid-template-columns: 1fr 1fr;
        }

        .fm01-features-hero {
            text-align: left;
            padding-top: 75px;
        }

        .fm01-feature-tabs {
            justify-content: flex-start;
        }
    }

    @media (max-width: 520px) {
        .fm01-grid {
            grid-template-columns: 1fr;
        }

        .fm01-features {
            padding-left: 18px;
            padding-right: 18px;
        }

        .fm01-features-hero h1 {
            font-size: 50px;
        }
    }
`;

const featureScript = `
(() => {
  const root = document.querySelector('.fm01-features');
  if (!root) return;
  const buttons = [...root.querySelectorAll('.fm01-feature-tabs button')];
  const sections = buttons.map(b => root.querySelector('#' + b.dataset.section)).filter(Boolean);
  buttons.forEach(btn => btn.addEventListener('click', () => {
    root.querySelector('#' + btn.dataset.section)?.scrollIntoView({behavior:'smooth', block:'start'});
  }));
  const io = new IntersectionObserver(entries => {
    const visible = entries.filter(e => e.isIntersecting).sort((a,b) => b.intersectionRatio-a.intersectionRatio)[0];
    if (!visible) return;
    buttons.forEach(b => b.classList.toggle('is-active', b.dataset.section === visible.target.id));
  }, {rootMargin:'-20% 0px -65% 0px', threshold:[0,.15,.5]});
  sections.forEach(s => io.observe(s));
})();
`;

export default function Page() {
    useEffect(() => {
        const root = document.querySelector('.fm01-features');
        if (!root) return;

        // Generic type argument tells TypeScript that elements are HTMLButtonElement instances
        const buttons = Array.from(
            root.querySelectorAll<HTMLButtonElement>('.fm01-feature-tabs button')
        );

        const sections = buttons
            .map((button) => {
                const sectionId = button.dataset.section;
                return sectionId ? root.querySelector('#' + sectionId) : null;
            })
            .filter((section): section is Element => Boolean(section));

        const syncActiveTab = (id: string) => {
            buttons.forEach((button) => {
                const isActive = button.dataset.section === id;
                button.classList.toggle('is-active', isActive);
                button.setAttribute('aria-selected', String(isActive));
            });
        };

        const clickHandlers = new Map<HTMLButtonElement, () => void>();

        buttons.forEach((button) => {
            const handleClick = () => {
                const sectionId = button.dataset.section;
                if (!sectionId) return;
                const section = root.querySelector('#' + sectionId);
                section?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            };

            clickHandlers.set(button, handleClick);
            button.addEventListener('click', handleClick);
        });

        const observer = new IntersectionObserver(
            (entries) => {
                const visible = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

                if (!visible) return;
                syncActiveTab(visible.target.id);
            },
            { rootMargin: '-20% 0px -65% 0px', threshold: [0, 0.15, 0.5] }
        );

        sections.forEach((section) => observer.observe(section));

        return () => {
            observer.disconnect();
            buttons.forEach((button) => {
                const handler = clickHandlers.get(button);
                if (handler) {
                    button.removeEventListener('click', handler);
                }
            });
        };
    }, []);

    return (
        <>
            <style>{styles}</style>

            <section className="fm01-features" aria-label="Feature overview">
                <div className="fm01-features-hero">
                    <div className="fm01-kicker">FEATURES</div>
                    <h1>
                        Everything your
                        <br />
                        <span>Discord server needs.</span>
                    </h1>
                    <p>
                        Moderation, security, music, logging, economy and more — all
                        working together in one bot.
                    </p>
                </div>

                <div className="fm01-feature-tabs" role="tablist" aria-label="Feature categories">
                    <button type="button" role="tab" className="is-active" data-section="moderation" aria-selected="true">
                        Moderation
                    </button>
                    <button type="button" role="tab" data-section="security" aria-selected="false">
                        Security
                    </button>
                    <button type="button" role="tab" data-section="music" aria-selected="false">
                        Music
                    </button>
                    <button type="button" role="tab" data-section="logging" aria-selected="false">
                        Logging
                    </button>
                    <button type="button" role="tab" data-section="more" aria-selected="false">
                        Everything else
                    </button>
                    <button type="button" role="tab" data-section="branding" aria-selected="false">
                        Branding
                    </button>
                </div>

                <section className="fm01-feature-row" id="moderation">
                    <div className="fm01-copy">
                        <small>01 / MODERATION</small>
                        <h2>
                            Keep your server
                            <br />
                            under control.
                        </h2>
                        <p>
                            Handle rule breakers quickly without turning moderation into a chore.
                            Cases, warnings, mutes, kicks, bans and other everyday controls stay
                            right where your staff already work: Discord.
                        </p>
                        <div className="fm01-chips">
                            <span>Warn</span>
                            <span>Mute</span>
                            <span>Kick</span>
                            <span>Ban</span>
                            <span>Unban</span>
                            <span>Cases</span>
                            <span>Slowmode</span>
                        </div>
                    </div>
                    <div className="fm01-demo discord-demo">
                        <div className="demo-channel"># mod-log</div>
                        <div className="demo-date">TODAY AT 14:32</div>
                        <div className="demo-msg">
                            <b>Pearoo</b>
                            <i>Today at 14:32</i>
                            <p>?!warn @rnxm 1w Hacking threats</p>
                        </div>
                        <div className="demo-result">
                            <strong>✓</strong>
                            <div>
                                <b>Case #184 created</b>
                                <small>Warning issued successfully</small>
                            </div>
                            <em>ACTIVE</em>
                        </div>
                        <div className="demo-msg bot">
                            <b>
                                fm01 <label>APP</label>
                            </b>
                            <i>Today at 14:32</i>
                            <p>
                                Warning recorded for <strong>@rnxm</strong>
                            </p>
                        </div>
                    </div>
                </section>

                <section className="fm01-feature-row reverse" id="security">
                    <div className="fm01-copy">
                        <small>02 / SECURITY</small>
                        <h2>
                            Protection that
                            <br />
                            works quietly.
                        </h2>
                        <p>
                            AutoMod filters forbidden phrases, links and Discord invites while
                            anti-spam, mention and message-line limits help keep abuse under
                            control.
                        </p>
                        <div className="fm01-chips">
                            <span>AutoMod</span>
                            <span>Phrase filter</span>
                            <span>Link filter</span>
                            <span>Invite filter</span>
                            <span>Anti-spam</span>
                            <span>Bypasses</span>
                        </div>
                    </div>
                    <div className="fm01-demo security-demo">
                        <div className="security-title">
                            <span>●</span>
                            <b>AutoMod</b>
                            <em>ACTIVE</em>
                        </div>
                        <div className="security-rule">
                            <b>Forbidden phrases</b>
                            <span>ON</span>
                            <small>Filtering enabled</small>
                        </div>
                        <div className="security-rule">
                            <b>Link filter</b>
                            <span>ON</span>
                            <small>Allowlist configured</small>
                        </div>
                        <div className="security-rule">
                            <b>Invite filter</b>
                            <span>ON</span>
                            <small>Blocked by default</small>
                        </div>
                        <div className="security-rule">
                            <b>Anti-spam</b>
                            <span>ON</span>
                            <small>5 messages / 5 seconds</small>
                        </div>
                        <div className="security-safe">
                            ✓ <div><b>Server protection active</b><small>No violations requiring action</small></div>
                        </div>
                    </div>
                </section>

                <section className="fm01-feature-row" id="music">
                    <div className="fm01-copy">
                        <small>03 / MUSIC</small>
                        <h2>
                            Your server&apos;s
                            <br />
                            soundtrack.
                        </h2>
                        <p>
                            Play and control music directly from Discord with queues, seeking,
                            volume, shuffle, looping and playback controls.
                        </p>
                        <div className="fm01-chips">
                            <span>Play</span>
                            <span>Pause</span>
                            <span>Queue</span>
                            <span>Seek</span>
                            <span>Shuffle</span>
                            <span>Loop</span>
                            <span>Volume</span>
                        </div>
                    </div>
                    <div className="fm01-demo music-demo">
                        <div className="album">♫</div>
                        <small>NOW PLAYING</small>
                        <h3>Never Gonna Give You Up</h3>
                        <p>Rick Astley</p>
                        <div className="progress">
                            <span />
                        </div>
                        <div className="times">
                            <span>1:42</span>
                            <span>3:32</span>
                        </div>
                        <div className="player-controls">
                            <b>↶</b>
                            <strong>Ⅱ</strong>
                            <b>↷</b>
                        </div>
                        <div className="queue">
                            <span>QUEUE</span>
                            <b>7 tracks</b>
                        </div>
                    </div>
                </section>

                <section className="fm01-feature-row reverse" id="logging">
                    <div className="fm01-copy">
                        <small>04 / LOGGING</small>
                        <h2>
                            Know what
                            <br />
                            happened.
                        </h2>
                        <p>
                            Keep an audit trail of the changes that matter: messages, members,
                            roles, channels, voice states, moderation actions, AutoMod and more.
                        </p>
                        <div className="fm01-chips">
                            <span>Messages</span>
                            <span>Members</span>
                            <span>Roles</span>
                            <span>Channels</span>
                            <span>Voice</span>
                            <span>AutoMod</span>
                        </div>
                    </div>
                    <div className="fm01-demo log-demo">
                        <div className="log-head">
                            <b>SERVER ACTIVITY</b>
                            <span>LIVE</span>
                        </div>
                        <div>
                            <time>14:41:08</time>
                            <b>Message deleted</b>
                            <small>#general · @Alex</small>
                        </div>
                        <div>
                            <time>14:40:52</time>
                            <b>Role updated</b>
                            <small>@Moderator</small>
                        </div>
                        <div>
                            <time>14:39:17</time>
                            <b>Member joined</b>
                            <small>@Nova</small>
                        </div>
                        <div>
                            <time>14:38:04</time>
                            <b>Channel created</b>
                            <small>#events</small>
                        </div>
                        <div>
                            <time>14:36:49</time>
                            <b>AutoMod action</b>
                            <small>Invite filter</small>
                        </div>
                    </div>
                </section>

                <section className="fm01-more" id="more">
                    <small>THE REST</small>
                    <h2>
                        And everything
                        <br />
                        in between.
                    </h2>
                    <p>
                        The core systems get the spotlight. Everything else makes fm01 feel
                        complete.
                    </p>
                    <div className="fm01-grid">
                        <article>
                            <b>Economy</b>
                            <p>
                                Balance, work, crime, daily rewards, transfers, slots, deposits
                                and a server shop.
                            </p>
                        </article>
                        <article>
                            <b>Giveaways</b>
                            <p>
                                Create giveaways with durations, winners, prizes and interactive
                                participation.
                            </p>
                        </article>
                        <article>
                            <b>Levels</b>
                            <p>
                                XP, leaderboards, rewards, channel multipliers and role
                                multipliers.
                            </p>
                        </article>
                        <article>
                            <b>Information</b>
                            <p>
                                Inspect users, servers, roles, channels, emojis and other Discord
                                resources.
                            </p>
                        </article>
                        <article>
                            <b>Localization</b>
                            <p>
                                Change the bot language from Discord and give your community the
                                experience it wants.
                            </p>
                        </article>
                        <article>
                            <b>Custom Messages</b>
                            <p>
                                Transform and generate messages with utilities ranging from ASCII to
                                QR codes.
                            </p>
                        </article>
                        <article>
                            <b>Join &amp; Leave</b>
                            <p>
                                Configure custom messages for members joining and leaving your
                                server.
                            </p>
                        </article>
                        <article>
                            <b>Snapshots</b>
                            <p>
                                Save and load server configuration when you need to restore your
                                setup.
                            </p>
                        </article>
                    </div>
                </section>

                <section className="fm01-branding" id="branding">
                    <div>
                        <small>CUSTOM BRANDING</small>
                        <h2>
                            Your server.
                            <br />
                            Your identity.
                        </h2>
                        <p>
                            Make fm01 fit your community instead of making your community fit the
                            bot.
                        </p>
                    </div>
                    <div className="brand-preview">
                        <div className="brand-icon">f</div>
                        <div>
                            <b>fm01</b>
                            <small>Built for your community</small>
                        </div>
                        <button type="button">Customize →</button>
                    </div>
                </section>
            </section>

            <style jsx global>{`
                .fm01-features {
                    --f-border: rgba(255, 255, 255, 0.09);
                    --f-muted: rgba(255, 255, 255, 0.58);
                    --f-card: rgba(255, 255, 255, 0.035);
                    max-width: 1180px;
                    margin: auto;
                    padding: 0 24px 100px;
                }

                .fm01-features-hero {
                    padding: 105px 0 65px;
                    text-align: center;
                }

                .fm01-kicker,
                .fm01-copy > small,
                .fm01-more > small,
                .fm01-branding small {
                    font-size: 10px;
                    letter-spacing: 0.17em;
                    font-weight: 800;
                    opacity: 0.58;
                }

                .fm01-features-hero h1 {
                    font-size: clamp(48px, 7vw, 88px);
                    line-height: 0.96;
                    letter-spacing: -0.06em;
                    margin: 17px 0 22px;
                }

                .fm01-features-hero h1 span {
                    opacity: 0.55;
                }

                .fm01-features-hero > p {
                    max-width: 620px;
                    margin: auto;
                    color: var(--f-muted);
                    line-height: 1.7;
                    font-size: 16px;
                }

                .fm01-feature-tabs {
                    position: sticky;
                    top: 0;
                    z-index: 4;
                    display: flex;
                    justify-content: center;
                    gap: 7px;
                    padding: 13px 0;
                    margin-bottom: 15px;
                    background: linear-gradient(to bottom, var(--site-background, transparent) 70%, transparent);
                    backdrop-filter: blur(14px);
                    overflow: auto;
                }

                .fm01-feature-tabs button {
                    border: 1px solid var(--f-border);
                    background: var(--f-card);
                    color: inherit;
                    opacity: 0.62;
                    border-radius: 999px;
                    padding: 9px 14px;
                    font: 600 11px inherit;
                    white-space: nowrap;
                    cursor: pointer;
                    transition: 0.2s;
                }

                .fm01-feature-tabs button:hover,
                .fm01-feature-tabs button.is-active {
                    opacity: 1;
                    background: rgba(255, 255, 255, 0.12);
                    border-color: rgba(255, 255, 255, 0.2);
                }

                .fm01-feature-row {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    align-items: center;
                    gap: 80px;
                    padding: 125px 0;
                    scroll-margin-top: 60px;
                }

                .fm01-feature-row.reverse .fm01-copy {
                    order: 2;
                }

                .fm01-feature-row.reverse .fm01-demo {
                    order: 1;
                }

                .fm01-copy h2,
                .fm01-more h2,
                .fm01-branding h2 {
                    font-size: clamp(40px, 5vw, 67px);
                    line-height: 0.98;
                    letter-spacing: -0.055em;
                    margin: 16px 0 24px;
                }

                .fm01-copy > p,
                .fm01-more > p,
                .fm01-branding p {
                    max-width: 530px;
                    color: var(--f-muted);
                    font-size: 15px;
                    line-height: 1.75;
                }

                .fm01-chips {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 7px;
                    margin-top: 26px;
                }

                .fm01-chips span {
                    font-size: 10px;
                    font-weight: 650;
                    border: 1px solid var(--f-border);
                    padding: 7px 9px;
                    border-radius: 7px;
                    opacity: 0.68;
                }

                .fm01-demo {
                    border: 1px solid var(--f-border);
                    background: var(--f-card);
                    border-radius: 17px;
                    box-shadow: 0 25px 70px rgba(0, 0, 0, 0.16);
                    overflow: hidden;
                }

                .discord-demo {
                    padding: 18px;
                }

                .demo-channel {
                    font-size: 11px;
                    font-weight: 700;
                    padding-bottom: 17px;
                    border-bottom: 1px solid var(--f-border);
                }

                .demo-date {
                    font-size: 8px;
                    letter-spacing: 0.1em;
                    opacity: 0.35;
                    margin: 17px 0 4px;
                }

                .demo-msg {
                    padding: 14px 0;
                }

                .demo-msg b {
                    font-size: 11px;
                }

                .demo-msg i {
                    font-style: normal;
                    font-size: 8px;
                    opacity: 0.35;
                    margin-left: 7px;
                }

                .demo-msg p {
                    font-size: 11px;
                    opacity: 0.68;
                    margin: 7px 0 0;
                }

                .demo-msg label {
                    font-size: 7px;
                    background: rgba(139, 124, 255, 0.35);
                    border-radius: 3px;
                    padding: 2px 4px;
                    margin-left: 3px;
                }

                .demo-result {
                    display: flex;
                    align-items: center;
                    gap: 11px;
                    padding: 13px;
                    border: 1px solid rgba(139, 124, 255, 0.2);
                    background: rgba(139, 124, 255, 0.07);
                    border-radius: 9px;
                }

                .demo-result > strong {
                    font-size: 16px;
                }

                .demo-result b {
                    display: block;
                    font-size: 10px;
                }

                .demo-result small {
                    font-size: 8px;
                    opacity: 0.45;
                }

                .demo-result em {
                    margin-left: auto;
                    font-style: normal;
                    font-size: 7px;
                    letter-spacing: 0.1em;
                    opacity: 0.6;
                }

                .security-demo {
                    padding: 19px;
                }

                .security-title {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 11px;
                    padding-bottom: 16px;
                    border-bottom: 1px solid var(--f-border);
                }

                .security-title span {
                    font-size: 8px;
                }

                .security-title em {
                    margin-left: auto;
                    font-style: normal;
                    font-size: 7px;
                    letter-spacing: 0.12em;
                    opacity: 0.5;
                }

                .security-rule {
                    position: relative;
                    padding: 16px 0;
                    border-bottom: 1px solid var(--f-border);
                }

                .security-rule b {
                    font-size: 10px;
                }

                .security-rule small {
                    display: block;
                    font-size: 8px;
                    opacity: 0.4;
                    margin-top: 4px;
                }

                .security-rule span {
                    position: absolute;
                    right: 0;
                    top: 18px;
                    font-size: 7px;
                    font-weight: 800;
                    opacity: 0.55;
                }

                .security-safe {
                    display: flex;
                    gap: 9px;
                    margin-top: 16px;
                    padding: 12px;
                    border-radius: 8px;
                    background: rgba(100, 220, 150, 0.06);
                    font-size: 11px;
                }

                .security-safe small {
                    display: block;
                    font-size: 8px;
                    opacity: 0.4;
                    margin-top: 3px;
                }

                .music-demo {
                    padding: 20px;
                    text-align: center;
                }

                .album {
                    height: 185px;
                    border-radius: 11px;
                    display: grid;
                    place-items: center;
                    font-size: 66px;
                    background: radial-gradient(circle at 35% 25%, rgba(150, 135, 255, 0.55), rgba(255, 255, 255, 0.03) 65%);
                }

                .music-demo > small {
                    display: block;
                    font-size: 7px;
                    letter-spacing: 0.16em;
                    opacity: 0.4;
                    margin-top: 20px;
                }

                .music-demo h3 {
                    font-size: 15px;
                    margin: 7px 0 3px;
                }

                .music-demo > p {
                    font-size: 9px;
                    opacity: 0.4;
                    margin: 0;
                }

                .progress {
                    height: 3px;
                    border-radius: 3px;
                    background: rgba(255, 255, 255, 0.09);
                    margin-top: 22px;
                }

                .progress span {
                    display: block;
                    width: 43%;
                    height: 100%;
                    background: currentColor;
                }

                .times {
                    display: flex;
                    justify-content: space-between;
                    font-size: 7px;
                    opacity: 0.35;
                    margin-top: 6px;
                }

                .player-controls {
                    display: flex;
                    justify-content: center;
                    gap: 24px;
                    align-items: center;
                    margin: 20px;
                }

                .player-controls strong {
                    font-size: 18px;
                }

                .player-controls b {
                    font-size: 14px;
                    opacity: 0.65;
                }

                .queue {
                    display: flex;
                    justify-content: space-between;
                    border-top: 1px solid var(--f-border);
                    padding-top: 14px;
                    font-size: 8px;
                    opacity: 0.55;
                }

                .log-demo {
                    padding: 18px;
                }

                .log-head {
                    display: flex;
                    justify-content: space-between;
                    font-size: 9px;
                    padding-bottom: 14px;
                    border-bottom: 1px solid var(--f-border);
                }

                .log-head span {
                    font-size: 7px;
                    letter-spacing: 0.1em;
                    opacity: 0.5;
                }

                .log-demo > div:not(.log-head) {
                    display: grid;
                    grid-template-columns: 68px 1fr auto;
                    gap: 10px;
                    padding: 14px 0;
                    border-bottom: 1px solid var(--f-border);
                    align-items: center;
                }

                .log-demo time {
                    font-size: 7px;
                    opacity: 0.3;
                }

                .log-demo b {
                    font-size: 9px;
                }

                .log-demo small {
                    font-size: 8px;
                    opacity: 0.4;
                }

                .fm01-more {
                    padding: 125px 0;
                    scroll-margin-top: 60px;
                }

                .fm01-grid {
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 10px;
                    margin-top: 45px;
                }

                .fm01-grid article {
                    border: 1px solid var(--f-border);
                    background: var(--f-card);
                    border-radius: 13px;
                    padding: 21px;
                    min-height: 155px;
                    transition: 0.2s;
                }

                .fm01-grid article:hover {
                    transform: translateY(-3px);
                    background: rgba(255, 255, 255, 0.055);
                }

                .fm01-grid b {
                    font-size: 12px;
                }

                .fm01-grid p {
                    font-size: 10px;
                    line-height: 1.65;
                    opacity: 0.48;
                    margin: 12px 0 0;
                }

                .fm01-branding {
                    display: grid;
                    grid-template-columns: 1fr 1fr;
                    gap: 70px;
                    align-items: center;
                    padding: 125px 0 145px;
                    scroll-margin-top: 60px;
                }

                .brand-preview {
                    border: 1px solid var(--f-border);
                    background: var(--f-card);
                    border-radius: 16px;
                    padding: 22px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                }

                .brand-icon {
                    width: 44px;
                    height: 44px;
                    border-radius: 11px;
                    background: rgba(255, 255, 255, 0.9);
                    color: #111;
                    display: grid;
                    place-items: center;
                    font-weight: 850;
                    font-size: 22px;
                }

                .brand-preview b {
                    font-size: 12px;
                }

                .brand-preview small {
                    display: block;
                    font-size: 8px;
                    opacity: 0.4;
                    margin-top: 3px;
                }

                .brand-preview button {
                    margin-left: auto;
                    background: rgba(255, 255, 255, 0.9);
                    color: #111;
                    border: 0;
                    border-radius: 7px;
                    padding: 9px 11px;
                    font: 700 9px inherit;
                }

                @media (max-width: 800px) {
                    .fm01-feature-row,
                    .fm01-branding {
                        grid-template-columns: 1fr;
                        gap: 45px;
                        padding: 90px 0;
                    }

                    .fm01-feature-row.reverse .fm01-copy,
                    .fm01-feature-row.reverse .fm01-demo {
                        order: initial;
                    }

                    .fm01-grid {
                        grid-template-columns: 1fr 1fr;
                    }

                    .fm01-features-hero {
                        text-align: left;
                        padding-top: 75px;
                    }

                    .fm01-feature-tabs {
                        justify-content: flex-start;
                    }
                }

                @media (max-width: 520px) {
                    .fm01-grid {
                        grid-template-columns: 1fr;
                    }

                    .fm01-features {
                        padding-left: 18px;
                        padding-right: 18px;
                    }

                    .fm01-features-hero h1 {
                        font-size: 50px;
                    }
                }
            `}</style>

            <script dangerouslySetInnerHTML={{ __html: featureScript }} />
        </>
    );
}
