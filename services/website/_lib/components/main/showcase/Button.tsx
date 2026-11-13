import { ButtonColors, ButtonType } from "@/_lib/types/MessageLang"
import { faArrowUpRightFromSquare, faBoxOpen, faLink } from "@fortawesome/free-solid-svg-icons"
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome"
import Link from "next/link"

const COLORS: Record<ButtonColors, string> = {
    [ButtonColors.PRIMARY]: "is-primary",
    [ButtonColors.SECONDARY]: "is-secondary",
    [ButtonColors.DANGER]: "is-danger",
    [ButtonColors.SUCCESS]: "is-success"
}

export default function Button({
    label,
    url,
    emoji,
    color,
    disabled
}: ButtonType) {
    if (url && color !== undefined) {
        throw new Error("A button can't have a preset color AND url at the same time.")
    }

    if (url && emoji) {
        throw new Error("A button can't have an emoji AND url at the same time.")
    }

    if (url) {
        return (
            <Link href={disabled ? "" : url} className={`url-button ${disabled ? "is-disabled" : ""}`}>
                <span>{label}</span>
                <FontAwesomeIcon icon={faArrowUpRightFromSquare} />
            </Link>
        )
    }

    if (color !== undefined) {
        return (
            <div className={`action-button ${COLORS[color]} ${disabled ? "is-disabled" : ""}`}>
                <span>{emoji}</span>
                <span>{label}</span>
            </div>
        )
    }

    return (
        <div className={`button action-button ${COLORS[ButtonColors.PRIMARY]} ${disabled ? "is-disabled" : ""}`}>
            <span>{emoji}</span>
            <span>{label}</span>
        </div>
    )
}