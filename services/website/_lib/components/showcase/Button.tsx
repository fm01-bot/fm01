import { ButtonColors, ButtonType } from "@/_lib/Types"
import { faArrowUpRightFromSquare, faBoxOpen, faLink } from "@fortawesome/free-solid-svg-icons"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"

export default function Button({
    label,
    url,
    emoji,
    color,
    disabled
}: ButtonType) {
    if (url && color) {
        throw new Error("A button can't have a preset color AND url at the same time.")
    }

    if (url && emoji) {
        throw new Error("A button can't have an emoji AND url at the same time.")
    }

    if (url) {
        return (
            <Link href={disabled ? "" : url} className={` ${disabled ? "opacity-50 hover:cursor-not-allowed!" : ""} rounded-lg bg-text/10 border border-text/30 px-2 py-1 flex items-center gap-1 hover:cursor-pointer grid-cols-subgrid col-span-1`}>
                {label}
                <FontAwesomeIcon icon={faArrowUpRightFromSquare} />
            </Link>
        )
    }

    if (color) {
        return (
            <>
                {label}
                {color}
                {emoji}
                {disabled}
            </>
        )
    }

    return (
        <>
            {label}
            {emoji}
            {disabled}
        </>
    )
}