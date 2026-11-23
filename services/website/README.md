# website

Build: docker build --target build .

Prod: docker build --target prod -t fm01-prod . && docker run -p 127.0.0.1:3007:3007 -e OG_IMAGE_SECRET=... fm01-prod

Publish the port on `127.0.0.1` only: the site is served through Caddy. `OG_IMAGE_SECRET` (any long random string) signs
the preview image links, so they stay valid across restarts. The prod server refuses to start without it.

Dev preview: fm01bot.gamrtag.xyz
