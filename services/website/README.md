# website

Dev run: docker build --target dev -t fm01-dev . && docker run -p 3007:3007 fm01-dev

Build: docker build --target build .

Prod: docker build --target prod -t fm01-prod . && docker run -p 3007:3007 fm01-prod