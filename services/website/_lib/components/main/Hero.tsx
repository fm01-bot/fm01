import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import '@lib/css/main/hero.css';
import Link from "next/link";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import { faDiscord } from "@fortawesome/free-brands-svg-icons";

export default function Hero({ lang }: { lang: MainPageLangJson["hero"] }) {
    return (
        <div className="hero-main">
            <div className="title">
                <h1 >{lang.title[0]}</h1>
                <h1 >{lang.title[1]}</h1>
                <h1 >{lang.title[2]}</h1>
            </div>
            <div className="subtext">
                <p>{lang.subtext[0]}</p>
                <p>{lang.subtext[1]}</p>
            </div>
            <div className="buttons">
                <Link href={`https://dashboard.fm01.bot/`}>
                    <FontAwesomeIcon icon={faDiscord} />
                    <span>
                        {lang.invite_btn}
                    </span>
                </Link>
                <Link href={`https://dc.fm01.bot/`}>
                    <span>
                        {lang.support_btn}
                    </span>
                </Link>
            </div>
        </div>
    );
}