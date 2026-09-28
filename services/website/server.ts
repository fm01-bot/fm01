import { createServer } from 'http'
import { parse } from 'url'
import next from 'next'
import schedule from 'node-schedule'
import translationFetcher from './translationFetcher'

const port = parseInt(process.env.PORT || '3007', 10)
const dev = process.env.NODE_ENV !== 'production'

const app = next({ dev })
const handle = app.getRequestHandler()

app.prepare().then(async () => {
    const server = createServer((req, res) => {
        const parsedUrl = parse(req.url || '', true)
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