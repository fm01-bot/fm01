import { EmbedType } from "@/_lib/Types";
import Button from "./Button";
import Field from "./Field";

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
        <>
            {title}
            {description}
            {url}
            {color}
            {fields?.map((f, i) => {
                return <Field key={i} {...f} />
            })}
            {footer}
            {image}
            {thumbnail}
            {author}
            {
                buttons?.map((row, rowIndex) => (
                    <div key={`row-${rowIndex}`} className="flex gap-2">
                        {row.map((btn, btnIndex) => {
                            if (!btn) return null;
                            return <Button key={`btn-${rowIndex}-${btnIndex}`} {...btn} />
                        })}
                    </div>
                ))
            }
        </>
    )
}