# Self-hosting fm01

Thank you for choosing **fm01** to power your server!
Self-hosting problems aren't covered on the official support server. If you run into one, please
[open an issue](https://github.com/fm01-bot/fm01/issues/new/choose) on GitHub.

Want to change the code instead of just running it? See [CONTRIBUTING.md](CONTRIBUTING.md).

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with the Compose plugin (`docker compose`)
- [Git](https://git-scm.com/)
- A Discord bot token from the [Developer Portal](https://discord.com/developers/applications)
  (enable all three privileged intents: **Presence**, **Server Members**, and **Message Content**)
- Optional: [`just`](https://github.com/casey/just) for the shortcut recipes in `justfile`

Install these for your hosting platform (Debian Linux recommended).

## 1. Clone the repository

This creates a local copy of the files that the bot uses.

```bash
git clone https://github.com/fm01-bot/fm01.git
cd fm01
```

## 2. Create `.env`

This file holds secrets (such as the bot token, which works like the bot's password) and configuration values.
Keep it private: anyone with the token can control your bot.

```bash
cp .env.example .env
```

Fill in at least:

| Variable            | Description                                                       |
|---------------------|-------------------------------------------------------------------|
| `TOKEN`             | Your bot token                                                    |
| `DB_PASSWORD`       | Any strong password; used to create the PostgreSQL database       |
| `LAVALINK_PASSWORD` | Any strong password; shared between the bot and Lavalink          |

Leave `DB_HOST=db`, `LAVALINK_URI=http://lavalink:2333` and the Redis URLs as they are because they point to the Compose
services. `DEBUG_TOKEN` is only needed for debug mode, `SENTRY_DSN` is optional, and the clustering settings should
stay at `BOT_MODE=standalone` for self-hosting.

## 3. Create `config.yml`

This file tells the bot who owns it, which modules to load and where to report errors.

```bash
cp services/bot/config.yml.example services/bot/config.yml
```

Then edit at least:

- `owner_ids`: replace with your own Discord user ID(s)
- `emojis`: set to emoji markdown your bot can use (e.g. `<:check:123456789012345678>`)
- `log_channel_id`: a **private** channel ID for runtime error reports, used when no `SENTRY_DSN` is set in `.env`
- `modules`: the cogs to load (`"*"` loads all of them)

## 4. Start the bot

```bash
docker compose up -d --build
```

Database migrations run automatically before the bot starts: the `migrations` service applies them, and the bot waits
for it to finish successfully.

Then check that it's running:

```bash
docker compose logs -f bot
```

## Managing the bot

| Task             | Command                         | `just` shortcut   |
|------------------|---------------------------------|-------------------|
| Start            | `docker compose up -d`          | `just up`         |
| Stop             | `docker compose down`           | `just down`       |
| Restart the bot  | `docker compose restart bot`    | `just restart bot`|
| View logs        | `docker compose logs -f bot`    | `just logs bot`   |
| Delete all data  | `docker compose down -v`        | `just destroy`    |

> [!WARNING]
> `docker compose down -v` / `just destroy` permanently deletes the database volume. Only use it when strictly necessary!

## Updating

Pull the latest code and rebuild; migrations run on their own:

```bash
git pull
docker compose up -d --build
```

## Production

The rest of this file is a cheat sheet for the maintainers running the official fm01. Self-hosters can skip it.

### Gateway proxy

Production runs a [gateway proxy](https://github.com/Gelbpunkt/gateway-proxy) that holds the shard connections to
Discord. The bot connects to the proxy instead, so restarting it replays the guild state from the proxy's cache instead
of identifying every shard again (Discord allows one IDENTIFY per 5 seconds). Self-hosters don't need it: leave
`DISCORD_GATEWAY_URL` unset and the bot connects to Discord directly.

To enable it, set in `.env`:

```bash
COMPOSE_PROFILES=gateway-proxy
DISCORD_GATEWAY_URL=ws://gateway-proxy:7878
SHARD_COUNT=32          # must match the proxy; the bot refuses to start otherwise
```

The proxy's shard count comes from Discord's recommendation; `curl localhost:7878/shard-count` prints it. Its intents
in `gateway-proxy.json` must match the bot's (`discord.Intents.all()`), since the bot's own IDENTIFY never reaches
Discord.

- `just deploy` checks out the latest release, rebuilds the bot and the migrations service, runs migrations, then restarts only the bot; the proxy keeps the shards
  connected. `just deploy v0.9.0` deploys (or rolls back to) a given release, and `just deploy main` the testing branch.
- `just deploy-proxy` recreates the proxy, which reconnects every shard. Use it for proxy upgrades and shard count
  changes only, and update `SHARD_COUNT` first when the count changes.

Voice sessions don't survive a bot restart: players that were playing stop and have to be started again.

### Weblate and the proxy (optional)

Two opt-in profiles:

- `proxy` runs Caddy with [`services/proxy/Caddyfile`](services/proxy/Caddyfile). It serves the website, the Public API
  and Weblate, and gets their TLS certificates. It publishes ports 80 and 443, so nothing else on the host may use
  them, and each domain's DNS must point at the host.
- `weblate` runs [Weblate](https://weblate.org) at `weblate.fm01.bot`. It has its own Postgres and Redis, apart from the
  bot's.

```bash
COMPOSE_PROFILES=proxy,weblate
WEBLATE_DB_PASSWORD=...           # Weblate's own database
WEBLATE_ADMIN_EMAIL=you@example.com
# WEBLATE_ADMIN_PASSWORD=...      # unset: a random one is printed in the first `docker compose logs weblate`
```

To run Weblate locally without the proxy, set `WEBLATE_ENABLE_HTTPS=0` and `WEBLATE_SITE_DOMAIN=localhost:8080`
(`WEBLATE_PORT` changes the port), run `docker compose up -d weblate`, and open <http://localhost:8080>.

Weblate sends no email until you configure SMTP (the `WEBLATE_EMAIL_*` variables in its
[Docker docs](https://docs.weblate.org/en/latest/admin/install/docker.html)).
