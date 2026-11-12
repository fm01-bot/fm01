import type { ReactNode } from "react";

export default function StringParser({ message }: { message: string }) {
    if (!message) return
    // @user / @role mentions, and #channel mentions (must start with a letter, so "Case #184" stays plain).
    const MENTION = String.raw`(?<!\w)(?:@[^\s]+|#[A-Za-z][\w-]*)`;
    const mentionPattern = new RegExp(`^${MENTION}$`);

    function renderMentions(text: string, keyPrefix: string): ReactNode[] {
        return text.split(new RegExp(`(${MENTION})`, "g")).map((part, index) =>
            mentionPattern.test(part) ? (
                <span className="mention" key={`${keyPrefix}-mention-${index}`}>{part}</span>
            ) : (
                part
            )
        )
    }

    function renderToken(token: string, key: string): ReactNode {
        const linkLabel = token.match(/^\[([^\]]+)\]\([^)]*\)$/)?.[1]
            ?? token.match(/^\(([^()]+)\)\[[^\]]+\]$/)?.[1]
        if (linkLabel !== undefined) {
            return <span className="link" key={key}>{renderContent(linkLabel, `${key}-link`)}</span>
        }

        if (token.length > 1 && token.startsWith("`") && token.endsWith("`")) {
            return <code key={key}>{token.slice(1, -1)}</code>
        }

        if (token.startsWith("***") && token.endsWith("***")) {
            return <strong key={key}><em>{renderContent(token.slice(3, -3), `${key}-bold-italic`)}</em></strong>
        }

        if (token.startsWith("**") && token.endsWith("**")) {
            return <strong key={key}>{renderContent(token.slice(2, -2), `${key}-bold`)}</strong>
        }

        if (token.startsWith("*") && token.endsWith("*")) {
            return <em key={key}>{renderContent(token.slice(1, -1), `${key}-italic`)}</em>
        }

        return <span className="mention" key={key}>{token}</span>
    }

    function renderContent(text: string, keyPrefix: string): ReactNode[] {
        const tokenPattern = new RegExp(String.raw`(\`[^\`\n]+\`|\*\*\*[^\n]+?\*\*\*|\*\*[^\n]+?\*\*|\*[^\n]+?\*|\[[^\]\n]+\]\([^)]*\)|\([^()\n]+\)\[[^\]]+\]|${MENTION})`, "g");
        const parts: ReactNode[] = []
        let lastIndex = 0
        let match: RegExpExecArray | null
        let tokenIndex = 0

        while ((match = tokenPattern.exec(text)) !== null) {
            if (match.index > lastIndex) {
                parts.push(...renderMentions(text.slice(lastIndex, match.index), `${keyPrefix}-plain-${tokenIndex}`))
            }

            parts.push(renderToken(match[0], `${keyPrefix}-token-${tokenIndex}`))
            lastIndex = match.index + match[0].length
            tokenIndex += 1
        }

        if (lastIndex < text.length) {
            parts.push(...renderMentions(text.slice(lastIndex), `${keyPrefix}-plain-${tokenIndex}`))
        }

        return parts
    }

    return (
        <p className="message-content">
            {renderContent(message, "message")}
        </p>
    )
}