import { EmbedType } from "@/_lib/types/EmbedLang";
import Button from "./Button";
import Field from "./Field";
import Link from "next/link";
import Image from "next/image";
import StringParser from "./StringParser";

function Author({ author }: EmbedType) {
    return (
        <>
            {author?.icon_url ? <Image src={author.icon_url} alt="Author icon" width={20} height={20} /> : <></>}
            {author?.name ? <span>{author.name}</span> : <></>}
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
        <div className="embed" style={{ "--embed-color": color ?? "gray" } as React.CSSProperties}>
            <div className="embed-main">
                <div className="embed-content">
                    <div>
                        {
                            author?.url ? (
                                <Link href={author.url} className="embed-author">
                                    <Author author={author} />
                                </Link>
                            ) : (
                                <div className="embed-author">
                                    <Author author={author} />
                                </div>
                            )
                        }
                    </div>
                    {
                        url ? (<Link href={url} className="embed-title">{title}</Link>) : (<h1 className="embed-title">{title}</h1>)
                    }
                    <span className="embed-description"><StringParser message={description ?? ""} /></span>
                    <div className="embed-fields">
                        {
                            fields?.map((f, i) => {
                                return <Field key={i} {...f} />
                            })
                        }
                    </div>
                </div>
                {
                    thumbnail ? (<Image src={thumbnail.url} alt="thumbnail image" width={50} height={50} className="embed-thumbnail" />) : (<></>)
                }
            </div>
            {
                image ? (<Image src={image.url} alt="embed image" width={100} height={100} className="embed-image" />) : (<></>)
            }
            <div className="embed-buttons">
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
                    <div className="embed-footer">
                        {
                            footer.icon_url ? (<Image src={footer.icon_url} alt="footer icon" width={15} height={15} className="embed-footer-icon" />) : (<></>)
                        }
                        {
                            footer.text ? (<span className="embed-footer-text">{footer.text}</span>) : (<></>)
                        }
                        <span className="embed-footer-dot">•</span>
                        <span className="embed-footer-time">{new Date().toLocaleDateString("en", { year: 'numeric', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>

                    </div>
                ) : (<></>)
            }
        </div>
    )
}