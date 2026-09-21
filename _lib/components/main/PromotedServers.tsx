import { getPromotedServers } from "@/_lib/functions/getPromotedServers";
import { getStatsCount } from "@/_lib/functions/getStatsCount";
import Members from "@/_lib/svg/Members";
import { PromotedServersJson } from "@/_lib/types/MainPageLang";
import { MainPageLangJson } from "@/_lib/types/MainPageLang";
import { faDiscord } from "@fortawesome/free-brands-svg-icons";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import Image from "next/image";
import Link from "next/link";

export default async function PromotedServers({ lang }: { lang: MainPageLangJson["servers"] }) {

    const { SERVERS } = await getPromotedServers();

    const { COUNTS } = await getStatsCount();

    const ROWS = getRows();

    function getRows(): PromotedServersJson[][] {
        if (!SERVERS?.length) return [];
        const midpoint = Math.ceil(SERVERS.length / 2);

        return [
            SERVERS.slice(0, midpoint),
            SERVERS.slice(midpoint),
        ];
    }

    return (
        <div id="features" className="h-fit">
            <p className="title">
                {lang.title}
            </p>
            <span className="trust-subtext">
                <span>
                    {`${lang.subtext[0]} `}
                </span>
                <span>
                    {`${COUNTS[0]}+`}
                </span>
                <span>
                    {` ${lang.subtext[1]} `}
                </span>
                <span>
                    {`${COUNTS[1]}+`}
                </span>
                <span>
                    {` ${lang.subtext[2]}`}
                </span>
            </span>
            <div className="flex flex-row flex-wrap gap-2 w-full max-w-full justify-center promoted-servers">
                {
                    ROWS.map((row: PromotedServersJson[], i: number) => {
                        return (
                            <div key={i} className="promoted-servers-row">
                                <div className="promoted-servers-track">
                                    {[row, row].map((trackRow: PromotedServersJson[], trackIndex: number) => (
                                        <div key={trackIndex} className="promoted-servers-group" aria-hidden={trackIndex === 1}>
                                            {
                                                trackRow.map((s: PromotedServersJson, j: number) => {
                                                    return (
                                                        <Link href={s.invite} key={j} tabIndex={trackIndex === 1 ? -1 : undefined} className="flex flex-row h-fit w-full p-4 pr-8 gap-2.5 bg-contrast rounded-2xl">
                                                            <Image src={s.icon} alt={s.name} width={60} height={60} className="rounded-lg" />
                                                            <div className="flex flex-col">
                                                                <span className="text-2xl font-semibold">{s.name}</span>
                                                                <span className="flex flex-row items-center gap-1">
                                                                    <Members width={20} height={15} className="opacity-100 dark:opacity-40 mt-1" />
                                                                    <span className=" leading-[normal]! text-xl! font-light! opacity-50">{new Intl.NumberFormat().format(s.count)} {lang.memberstext}</span>
                                                                </span>
                                                            </div>
                                                        </Link>
                                                    )
                                                })
                                            }
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )
                    })
                }
            </div>

            <div className=" w-full items-center flex justify-center mt-20 -mb-20 text-white">
                <Link href={`add.fm01.bot`} className=" flex items-center justify-center gap-2 py-3 px-6 bg-primary w-fit rounded-2xl text-2xl font-extrabold hover:shadow-primary shadow-transparent shadow-[0px_0px_20px_0px]">
                    <FontAwesomeIcon icon={faDiscord} />
                    <span className=" font-extrabold">Join Them!</span>
                </Link>
            </div>
        </div>
    );
}