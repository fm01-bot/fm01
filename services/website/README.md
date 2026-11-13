# website

Build: docker build --target build .

Prod: docker build --target prod -t fm01-prod . && docker run -p 3007:3007 fm01-prod

Dev preview: fm01bot.gamrtag.xyz
