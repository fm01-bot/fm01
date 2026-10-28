import Link from "next/link";
import { MainPageLangJson, PremiumTierLangJson } from "@/_lib/types/MainPageLang";
import { faAdd, faCircleCheck, faCoins, faMailBulk } from "@fortawesome/free-solid-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";

function FeatureList({ feats }: { feats: string[] }) {
    return (
        <>
            {
                feats.map((a, i) => (
                    <span key={i}>
                        <FontAwesomeIcon icon={faCircleCheck} className="w-6! h-3.5! my-1.25" />
                        <span>{a}</span>
                    </span>
                ))
            }
        </>
    )
}

export default function Premium({ lang }: { lang: MainPageLangJson["premium"] }) {
    const FREE = lang.tiers.free;
    const PREMIUM = lang.tiers.premium;
    const CUSTOM = lang.tiers.custom;

    const TIERS = [
        {
            "name": "FREE",
            "obj": FREE,
            "button": <Link href={"https://add.fm01.bot"} target="_blank" className="button">
                <FontAwesomeIcon icon={faAdd} /> {FREE.button}
            </Link>
        },
        {
            "name": "PREMIUM",
            "obj": PREMIUM,
            "button": <Link href={"https://dashboard.fm01.bot"} target="_blank" className="button">
                <FontAwesomeIcon icon={faCoins} /> {PREMIUM.button}
            </Link>
        },
        {
            "name": "CUSTOM",
            "obj": CUSTOM,
            "button": <Link href="mailto:sales@fm01.bot" target="_blank" className="button">
                <FontAwesomeIcon icon={faMailBulk} /> {CUSTOM.button}
            </Link>
        },
    ]


    return (
        <div id="premium" className="h-fit">
            <p className="title">
                {lang.title}
            </p>
            <p className="subtext">
                {lang.subtext}
            </p>
            <div className="tier-container">
                {
                    TIERS.map((e, i) => {
                        const name: string = e.name;
                        const tier: PremiumTierLangJson = e.obj;
                        return (
                            <div key={i} id={name} className="tier-cards">
                                <div className="inner-container">
                                    <div className="top">
                                        <span className="tier-title">
                                            {tier.name}
                                        </span>
                                        <span className="tier-price">
                                            {tier.price}
                                        </span>
                                    </div>
                                    <div className="features w-full!">
                                        <FeatureList feats={tier.features} />
                                    </div>
                                </div>
                                {e.button}
                            </div>
                        )
                    })
                }
            </div>
            <p className="premium-disclamer">{lang.disclosure}<Link href={`https://github.com/fm01-bot`} className="link">GitHub</Link>.</p>
        </div >
    );
}