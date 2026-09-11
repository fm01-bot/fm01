# fm01
Self-host the entire fm01 ecosystem with a simple Docker command.

## Repository goal
This repository contains every service that we provide from other, different repos (as git subtrees), and a Docker Compose file.

As an end user, if you'd like to self-host the bot with every required service up and running,
all you need to do is run `docker compose up -d` after cloning this repo.

## Contribution notice
We never commit into this repo if we want to make changes to our service. Every service has its own repo for that.

For this reason, we most likely won't be accepting pull requests that often.

In the future, we might use this repo's Issues tab for every bug or enchancement you have with fm01.

<sub>maintainer cheat sheet: `git subtree add --prefix=[directoryName] https://github.com/fm01-bot/[repo].git main --squash`</sub>