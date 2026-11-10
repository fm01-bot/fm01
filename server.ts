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
        const requestUrl = new URL(
            req.url || '/',
            `http://${req.headers.host || 'localhost'}`
        )
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

    await translationFetcher()

    schedule.scheduleJob('0 0 * * *', async () => {
        await translationFetcher()
    })
})