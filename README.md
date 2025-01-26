# USSplitter

This is an addon for [usdb_syncer](https://github.com/bohning/usdb_syncer). It splits a downloaded songs mp3 into its vocals and instrumental with [demucs](https://github.com/adefossez/demucs), saves them alongside, and writes the correct tags to the .txt.

## Structure

USSplitter comes in two parts:

1. Server: The server component is a web server written with flask. It recieves input mp3 files, processes them, and offers the vocals and the instrumental back.
2. Addon: The addon interacts with usdb_syncer, processes the song, sends it to the server, then recieves vocals and instrumental back.

You need both to run this addon.

## Motivation

Stem separation is resource-intensive. This allows a powerful server, ideally cuda-accelerated, to split the files while usdb_syncer is run on a light machine. Of course, it possible to just run the server on the same machine if you wish.

Additionally, the approach is modular. For example, it would be very easy to write a script that runs through an entire song library, splitting everything. USSplitter provides a simple interface, manages resources, and can be expanded at will. 

## Current problems

- cannot change existing `#VOCALS` or `INSTRUMENTAL` tags. 
- uses internal methods of usdb_syncer. This could break the addon in future releases
- since there are no standards for addons, for example regarding their configuration, I have simply created some. These aren't great, so they will almost certainly change. 

## Install

> [!CAUTION]
> This is entirely untested on linux and macos. There isn't a whole lot that could happen, but still.

> [!WARNING]
> You should be somewhat technically inclined to use this. There are almost certainly bugs. Please make sure you backup your songs.

> [!WARNING] 
> This project is in its very early stages. Best results are achieved with a nvidia graphics card, although it *should* fallback to cpu. Note that the docker image is currently enormous (~8GB). This may or may not change.

> [!WARNING]
> Stem separation uses quite a lot of ram. I don't recommend using this with less than 16GB of system memory. Future updates will allow using smaller models, allowing for a smaller memory footprint.

### Required

- git
- docker

### Setup

clone this repository with 

`git clone https://github.com/randompersona1/ussplitter`

`cd ussplitter`

### Building the server

> [!NOTE]
> This can take a couple of minutes

`docker build -t ussplitter`

### Running the server

`docker run --name ussplitter -p 5000:5000 --gpus all ussplitter`

If there are no errors now, you should be fine.

### Configure the addon

Grab the addon file from `src/usdb_addon/ussplitter.py`. Put the python file into your usdb_syncer addons folder. On windows, this is located at `%LOCALAPPDATA%\bohning\usdb_syncer\addons`

The addon needs to be configured. I have decided to use an `addon_config` directory next to `addons`. This will almost certainly change in the future.

Create the `addon_config` directory and a `ussplitter.txt` inside it. The only configuration needed is a line with `SERVER_URI=http://localhost:5000`.

## Manual usage

If you don't want to use docker, you will need `uv` to manage the project. Currently, `gunicorn` is used, which does not work on windows. Replace it with a different wsgi server like waitress. For gunicorn, the run command is:

`uv run gunicorn -b 0.0.0.0:5000 -w 1 ussplitter.server:app`

Do not use more than one worker. Instead of a database, pure python is used, meaning workers cannot share data.
