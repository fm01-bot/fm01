import { createServer } from 'http'
import type { ParsedUrlQuery } from 'querystring'
import next from 'next'
import schedule from 'node-schedule'
import translationFetcher from './translationFetcher'

const port = parseInt(process.env.PORT || '3007', 10)
const dev = process.env.NODE_ENV !== 'production'

const app = next({ dev })
const handle = app.getRequestHandler()

app.prepare().then(async () => {
    const server = createServer((req, res) => {
        let requestUrl: URL
        try {
            // A fixed base: a path like `//:99999` would otherwise be read as a host and make `new URL` throw,
            // and an exception here would end the process.
            requestUrl = new URL(`http://localhost${req.url || '/'}`)
        } catch {
            res.writeHead(400).end()
            return
        }
        const query: ParsedUrlQuery = {}

        requestUrl.searchParams.forEach((value, key) => {
            const currentValue = query[key]
            query[key] = currentValue
                ? Array.isArray(currentValue)
                    ? [...currentValue, value]
                    : [currentValue, value]
                : value
        })

        const parsedUrl = {
            auth: null,
            hash: null,
            hostname: null,
            href: `${requestUrl.pathname}${requestUrl.search}`,
            pathname: requestUrl.pathname,
            protocol: null,
            search: requestUrl.search || null,
            slashes: null,
            port: null,
            query,
        }
        handle(req, res, parsedUrl)
    })

    if (dev) {
        server.on('upgrade', (req, socket, head) => {
            app.getUpgradeHandler()(req, socket, head)
        })
    }

    server.listen(port, () => {
        console.log(
            `> Server listening at http://localhost:${port} as ${dev ? 'dev' : process.env.NODE_ENV}`
        )
    })

    const refreshTranslations = async () => {
        try {
            await translationFetcher()
        } catch (error) {
            console.error('[translations] Failed to fetch bot translations:', error)
        }
    }

    await refreshTranslations()

    schedule.scheduleJob('0 0 * * *', refreshTranslations)
})