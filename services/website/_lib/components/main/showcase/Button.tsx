import { ButtonColors, ButtonType } from "@/_lib/types/MessageLang"
import { faArrowUpRightFromSquare, faBoxOpen, faLink } from "@fortawesome/free-solid-svg-icons"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"

const COLORS: Record<ButtonColors, string> = {
    [ButtonColors.PRIMARY]: "bg-primary hover:bg-primary/80",
    [ButtonColors.SECONDARY]: "bg-secondary hover:bg-secondary/80",
    [ButtonColors.DANGER]: "bg-red hover:bg-red/80",
    [ButtonColors.SUCCESS]: "bg-green hover:bg-green/80"
}

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
            <Link href={disabled ? "" : url} className={` ${disabled ? "opacity-50 hover:cursor-not-allowed!" : ""} button rounded-lg bg-text/10 border border-text/30 px-2 py-1 flex items-center gap-1 hover:cursor-pointer grid-cols-subgrid col-span-1`}>
                <span className=" text-base">{label}</span>
                <FontAwesomeIcon icon={faArrowUpRightFromSquare} />
            </Link>
        )
    }

    if (color) {
        return (
            <div className={`${COLORS[color]} ${disabled ? "opacity-50 hover:cursor-not-allowed!" : ""}`}>
                <span className="text-lg">{emoji}</span>
                <span className=" text-base">{label}</span>
            </div>
        )
    }

    return (
        <div className={`button ${COLORS[ButtonColors.PRIMARY]} ${disabled ? "opacity-50 hover:cursor-not-allowed!" : ""}`}>
            <span className="text-lg">{emoji}</span>
            <span className=" text-base">{label}</span>
        </div>
    )
}