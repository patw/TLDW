# TLDW

I don't have time to watch all this Youtube content.  TLDW will accept a youtube URL, download the transcript for the video, and summarize it with an LLM (even a local one!).  

![Main UI](screenshot.png)

## Installation

```
python -m venv tldw-env
source tldw-env/bin/activate
pip install -r requirements.txt
```

## Configuration

Open the config tab and add in the baseurl, api key and model name for summaries.  You can also configure the system message and the summary prompt.

## Running

Run either tldw.bat or tldw.sh to start app.

## Usage

Paste in a youtube url and hit summarize video

## Updating

Youtube seems to regularly break youtube-transcript-api.  You may need to git pull this code once in a while and run:

```
pip install --upgrade youtube-transcript-api
```