import { Octokit } from "@octokit/core";
import path from 'path'
import fs from 'fs/promises'
import { extractResponse, findByKey, findSubtree, type ResponseTarget } from './_lib/functions/responseExtractor'

type LocaleEntry = {
    name: string;
    download_url: string;
};

/**
 * Which bot response each website section shows. Paths are hints, not requirements: the
 * extractor searches the module subtree, so these keep working when the bot reorganises
 * its localization files.
 */
const targets: Record<string, Record<string, ResponseTarget>> = {
    warn: { embed: { root: "mod.warn", prefer: ["response"], avoid: ["unwarned", "notify"] } },
    giveaway: { embed: { root: "giveaway", prefer: ["active", "start", "response"], buttonFallback: true } },
    work: { embed: { root: "work" } },
    music: { embed: { root: "voice.play", prefer: ["now_playing"] } },
    info: {
        user: { root: "info.user", prefer: ["not_member"] },
        server: { root: "info.server" },
        role: { root: "info.role" },
    },
}

const isStringArray = (value: unknown): value is string[] =>
    Array.isArray(value) && value.every((item) => typeof item === "string")

function buildBotLocale(data: unknown, previous: Record<string, Record<string, unknown>> = {}, lang: string) {
    const result: Record<string, Record<string, unknown>> = {}

    for (const [section, entries] of Object.entries(targets)) {
        result[section] = { ...previous[section] }
        for (const [key, target] of Object.entries(entries)) {
            try {
                const response = extractResponse(data, target)
                if (response) result[section][key] = response
                else console.warn(`[translations] ${lang}: no response found for ${section}.${key} (kept previous value)`)
            } catch (error) {
                console.warn(`[translations] ${lang}: failed to extract ${section}.${key} (kept previous value)`, error)
            }
        }
    }

    const random = findByKey(findSubtree(data, "work"), "random", isStringArray)
    if (random) result.work.random = random

    return result
}

export default async function translationFetcher() {

    const octokit = new Octokit({ auth: process.env.GITHUB_TOKEN });

    const response = await octokit.request("GET /repos/{org}/{repo}/contents/{path}", {
        org: "fm01-bot",
        repo: "bot",
        path: "localization"
    });

    const locales = response.data
        .filter(
            (entry: typeof response.data): entry is LocaleEntry =>
                entry.type === "file" &&
                entry.name.endsWith(".l10n.json") &&
                typeof entry.download_url === "string",
        )
        .map((entry: typeof response.data) => ({
            lang: entry.name.replace(/\.l10n\.json$/, ""),
            url: entry.download_url,
        }));

    await Promise.all(
        locales.map(async ({ lang, url }: { lang: string, url: string }) => {
            try {
                const data = await (await fetch(url)).json();

                const file = path.resolve(`_lib/translations`, `${lang}.json`)
                const localData = JSON.parse(await fs.readFile(file, "utf-8"))
                localData['bot-locale'] = {
                    ...localData["bot-locale"],
                    ...buildBotLocale(data, localData["bot-locale"], lang),
                }

                await fs.writeFile(file, JSON.stringify(localData, null, 2), 'utf-8');
            } catch (error) {
                console.error(`[translations] Failed to update locale "${lang}":`, error)
            }
        })
    )
}
