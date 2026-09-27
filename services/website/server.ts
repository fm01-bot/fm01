import { createServer } from 'http'
import next from 'next'
import schedule from 'node-schedule'
import translationFetcher from './translationFetcher'

const port = parseInt(process.env.PORT || '3007', 10)
const dev = process.env.NODE_ENV !== 'production'
const app = next({ dev })
const handle = app.getRequestHandler()

app.prepare().then(async () => {
    createServer((req, res) => {
        handle(req, res)
    }).listen(port)

    await translationFetcher()

    schedule.scheduleJob('0 0 * * *', async () => {
        await translationFetcher()

    })

    console.log(
        `> Server listening at http://localhost:${port} as ${dev ? 'dev' : process.env.NODE_ENV
        }`
    )
})