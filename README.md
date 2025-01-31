# USSplitter

This is an addon for [usdb_syncer](https://github.com/bohning/usdb_syncer). It splits a downloaded songs mp3 into its vocals and instrumental with [demucs](https://github.com/adefossez/demucs), saves them alongside, and writes the correct tags to the .txt.

## Structure

USSplitter comes in two parts:

1. Server: The server component is a web server written with flask. It recieves input mp3 files, processes them, and offers the vocals and the instrumental back.
2. Addon: The addon interacts with usdb_syncer, processes the song, sends it to the server, then recieves vocals and instrumental back.

You need both to run this addon.

## Motivation

Stem separation is resource-intensive. USSplitter allows a powerful server, ideally cuda-accelerated, to split the files while usdb_syncer is run on a light machine. Of course, it is possible to just run the server on the same machine if you wish.

Additionally, the approach is modular. For example, it would be very easy to write a script that runs through an entire song library, splitting everything. USSplitter provides a simple interface, manages resources, and can be expanded at will. 

## Current problems

- cannot change existing `#VOCALS` or `INSTRUMENTAL` tags. 
- uses internal methods of usdb_syncer. This could break the addon in future releases of usdb_syncer
- since there are no standards for addons, for example regarding their configuration, I have simply created some. These aren't great, so they will almost certainly change. 

## Install

> [!CAUTION]
> This is untested on macos. If you have a mac and can confirm the addon works, please leave a comment.

> [!WARNING]
> You should be somewhat technically inclined to use the addon. There are probably certainly bugs. Please make sure you backup your songs.

> [!WARNING]
> Best results are achieved with a nvidia gpu. If you don't have one, you should only use the `htdemucs` model. On my Ryzen 5900x, separating with `htdemucs` takes ~70 seconds.

> [!WARNING]
> Stem separation uses quite a lot of ram. I don't recommend using the addon with less than 16GB of system memory.

### Required

- git
- docker

### Setup

clone this repository with 

`git clone https://github.com/randompersona1/ussplitter`

`cd ussplitter`

### Building the server

> [!NOTE]
> This can take a couple of minutes. The resulting image is ~7GB big.

`docker build -t ussplitter`

### Running the server

`docker run --name ussplitter -p 5000:5000 --gpus all ussplitter`

If there are no errors now, you should be fine.

### Configure the addon

Grab the addon file from `src/usdb_addon/ussplitter.py`. Put the python file into your usdb_syncer addons folder. On windows, this is located at `%LOCALAPPDATA%\bohning\usdb_syncer\addons`

The addon needs to be configured. I have decided to use an `addon_config` directory next to `addons`. This will almost certainly change in the future.

Create the `addon_config` directory and a `ussplitter.txt` inside it (or copy it from `src/usdb_addon/ussplitter.txt`). The file follows a basic line-separated `KEY=VALUE` structure. The following options are implemented:

| Option name | Value | Required | Default |
| ----------- | ----- | -------- | ------- |
| SERVER_URI  | base uri of the server you want to connect to, e.g. http://localhost:5000 | yes |  |
| DEMUCS_MODEL | the model you want to use. See [demucs](https://github.com/adefossez/demucs) for the list of models. I recommend `htdemucs`. Use `htdemucs_ft` if you have a cuda GPU and want a tiny bit of extra clarity. Note that quantised models (ending in `_q`) currently do not work | no | htdemucs


## Manual usage

If you don't want to use docker, you will need [`uv`](https://docs.astral.sh/uv/) to manage the project. Then, install the dependancies with `uv sync --group torch`.

To start the server, run:

`uv run --no-dev --group torch waitress --listen 0.0.0.0:5000 ussplitter.server:app`


## Development

You need [`uv`](https://docs.astral.sh/uv/) to manage the project.

You need a C compiler (like gcc) for `usdb_syncer`.

Run `uv sync` to install dependancies. If for some reason you want to install demucs and torch, add `--group=torch`. This is not default because torch is a large dependancy and not required for the addon. If you intend to modify the backend, you might want to install them.

Once the dependancies have been installed, use `ruff check` and `ruff format --diff` to lint. You should also use `isort --diff` to check your imports.
