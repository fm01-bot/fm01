import { EmbedType } from "@/_lib/Types";
import Button from "./Button";
import Field from "./Field";
import Link from "next/link";
import Image from "next/image";

function Author({ author }: EmbedType) {
    return (
        <>
            {author?.icon_url ? <Image src={author.icon_url} alt="Author icon" width={20} height={20} /> : <></>}
            {author?.name ? <span className="text-xs">{author.name}</span> : <></>}
        </>
    )
}

export default function Embed({
    title,
    description,
    url,
    color,
    fields,
    footer,
    image,
    thumbnail,
    author,
    buttons
}: EmbedType) {

    return (
        <div className={`bg-black/20 p-3 rounded-md gap-2 flex flex-col w-fit`} style={{ borderWidth: color ? "0px 0px 0px 6px" : "0px", borderColor: color }}>
            <div className="flex flex-row gap-5 w-fit">
                <div className="gap-1 flex flex-col">
                    <div>
                        {
                            author?.url ? (
                                <Link href={author.url} className="flex items-center justify-center w-fit gap-2">
                                    <Author author={author} />
                                </Link>
                            ) : (
                                <div className="flex items-center justify-center w-fit gap-2">
                                    <Author author={author} />
                                </div>
                            )
                        }
                    </div>
                    {
                        url ? (<Link href={url} className=" font-bold! text-base!">{title}</Link>) : (<h1 className=" font-bold! text-base!">{title}</h1>)
                    }
                    <p className="text-sm font-light!">{description}</p>
                    <div className="grid grid-cols-3 gap-3">
                        {
                            fields?.map((f, i) => {
                                return <Field key={i} {...f} />
                            })
                        }
                    </div>
                </div>
                {
                    thumbnail ? (<Image src={thumbnail.url} alt="thumbnail image" width={50} height={50} className="rounded-md h-fit w-fit" />) : (<></>)
                }
            </div>
            {
                image ? (<Image src={image.url} alt="embed image" width={100} height={100} className="w-full h-auto" />) : (<></>)
            }
            <div className="flex gap-2 flex-wrap">
                {
                    buttons?.map((btn, btnIndex) => {
                        if (!btn) return null;
                        return <Button key={`btn-${btnIndex}`} {...btn} />
                    }
                    )
                }
                    </div>
            {
                footer ? (
                    <div className="flex flex-row items-center gap-2">
                        {
                            footer.icon_url ? (<Image src={footer.icon_url} alt="footer icon" width={10} height={10} />) : (<></>)
                        }
                        {
                            footer.text ? (<span className=" text-sm -mb-1.5 text-text/50">{footer.text}</span>) : (<></>)
                        }
                        <span className="text-text/20 text-sm -mb-1.5">●</span>
                        <span className='text-xs mt-1.5 text-text/50'>{new Date().toLocaleDateString("en", { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>

                    </div>
                ) : (<></>)
            }
        </div >
    )
}