import { createServer } from 'http'
import { parse } from 'url'
import next from 'next'
import schedule from 'node-schedule'
import translationFetcher from './translationFetcher'

const port = parseInt(process.env.PORT || '3007', 10)
const dev = process.env.NODE_ENV !== 'production'

const app = next({ dev, hostname: 'localhost', port })
const handle = app.getRequestHandler()

app.prepare().then(async () => {
    const server = createServer((req, res) => {
        const parsedUrl = parse(req.url || '', true)
        handle(req, res, parsedUrl)
    })

    // Catch the WebSocket upgrade request and pass it to Next.js HMR
    server.on('upgrade', (req, socket, head) => {
        const parsedUrl = parse(req.url || '', true)
        if (parsedUrl.pathname === '/_next/webpack-hmr') {
            app.getUpgradeHandler()(req, socket, head)
        }
    })

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