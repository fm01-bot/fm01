import { Octokit } from "@octokit/core";
import path from 'path'
import fs from 'fs/promises'
type LocaleEntry = {
    name: string;
    download_url: string;
};

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

    console.log(locales)

    await Promise.all(
        locales.map(async ({ lang, url }: { lang: string, url: string }) => {
            const data = await (await fetch(url)).json();

            const file = path.resolve(`_lib/translations`, `${lang}.json`)
            const localData = JSON.parse(await fs.readFile(file, "utf-8"))
            localData['bot-locale'] = {
                ...localData["bot-locale"],
                "warn": {
                    "embed": data.mod.warn.response.embeds[0]
                },
                "giveaway": {
                    "embed": {
                        ...data.giveaway.start.response.embeds[0],
                        buttons: [
                            {
                                "label": data.giveaway.message.button
                            }
                        ]
                    }
                },
                "work": {
                    "embeds": data.work.embeds,
                    "random": data.work.random
                },
                "music": {
                    "embed": data.voice.play.now_playing.embeds[0]
                },
                "info": {
                    "user": data.info.user.not_member.embeds[0],
                    "server": data.info.server.embeds[0],
                    "role": data.info.role.embeds[0]
                }
            }
            localData['bot-locale']['warn'] = data.mod.warn.response.embeds

            await fs.writeFile(file, JSON.stringify(localData, null, 2), 'utf-8');

        })
    )

    console.log(response.data)
}