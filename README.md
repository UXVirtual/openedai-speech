OpenedAI Speech
---------------

An OpenAI API compatible text to speech server.

* Compatible with the OpenAI audio/speech API
* Serves the [/v1/audio/speech endpoint](https://platform.openai.com/docs/api-reference/audio/createSpeech)
* Not affiliated with OpenAI in any way, does not require an OpenAI API Key
* A free, private, text-to-speech server with custom voice cloning

Full Compatibility:
* `tts-1`: `alloy`, `echo`, `fable`, `onyx`, `nova`, and `shimmer` (configurable)
* `tts-1-hd`:  `alloy`, `echo`, `fable`, `onyx`, `nova`, and `shimmer` (configurable, uses OpenAI samples by default)
* response_format: `mp3`, `opus`, `aac`, or `flac`
* speed 0.25-4.0 (and more)

Details:
* model 'tts-1' via [piper tts](https://github.com/rhasspy/piper) (fast, can use cpu)
* model 'tts-1-hd' via [coqui-ai/TTS](https://github.com/coqui-ai/TTS) xtts_v2 voice cloning (fast, but requires around 4GB GPU VRAM)
* Can be run without TTS/xtts_v2, entirely on cpu
* Custom cloned voices can be used for tts-1-hd, just save a WAV file in the `/voices/` directory
* You can map your own [piper voices](https://rhasspy.github.io/piper-samples/) and xtts_v2 speaker clones via the `voice_to_speaker.yaml` configuration file
* Occasionally, certain words or symbols may sound incorrect, you can fix them with regex via `pre_process_map.yaml`

If you find a better voice match for `tts-1` or `tts-1-hd`, please let me know so I can update the defaults.


Version: 0.9.0, 2024-04-23

* Fix bug with yaml and loading UTF-8
* New sample text-to-speech application `say.py`
* Smaller docker base image
* Add beta [parler-tts](https://huggingface.co/parler-tts/parler_tts_mini_v0.1) support (you can describe very basic features of the speaker voice), See: (https://www.text-description-to-speech.com/) for some examples of how to describe voices. Voices can be defined in the `voice_to_speaker.yaml`.
* 2 example [parler-tts](https://huggingface.co/parler-tts/parler_tts_mini_v0.1) voices are included in the `voice_to_speaker.yaml` file.
* parler-tts is experimental software and is kind of slow. The exact voice will be slightly different each generation but should be similar to the basic description.

Version: 0.8.0, 2024-03-23

* Cleanup, docs update.

Version: 0.7.3, 2024-03-20

* Allow different xtts versions per voice in `voice_to_speaker.yaml`, ex. xtts_v2.0.2
* Quality: Fix xtts sample rate (24000 vs. 22050 for piper) and pops
* use CUDA 12.2-base in Dockerfile

API Documentation
-----------------

* [OpenAI Text to speech guide](https://platform.openai.com/docs/guides/text-to-speech)
* [OpenAI API Reference](https://platform.openai.com/docs/api-reference/audio/createSpeech)


Installation instructions
-------------------------

You can run the server via docker like so (**recommended**):
```shell
docker compose up
```
If you want a minimal docker image with piper support only (900MB vs. 13.5GB, see: Dockerfile.min). You can edit the `docker-compose.yml` to easily change this.

Manual instructions:
```shell
# Install the Python requirements
pip install -r requirements.txt
# install ffmpeg and curl
sudo apt install ffmpeg curl
# Download the voice models:
# for tts-1
bash download_voices_tts-1.sh
# and for tts-1-hd
bash download_voices_tts-1-hd.sh
```

Usage
-----

```
usage: speech.py [-h] [--piper_cuda] [--xtts_device XTTS_DEVICE] [--preload PRELOAD] [-P PORT]
                 [-H HOST]

OpenedAI Speech API Server

options:
  -h, --help            show this help message and exit
  --piper_cuda          Enable cuda for piper. Note: --cuda/onnxruntime-gpu is not working for me,
                        but cpu is fast enough (default: False)
  --xtts_device XTTS_DEVICE
                        Set the device for the xtts model. The special value of 'none' will use
                        piper for all models. (default: cuda)
  --preload PRELOAD     Preload a model (Ex. 'xtts' or 'xtts_v2.0.2'). By default it's loaded on
                        first use. (default: None)
  -P PORT, --port PORT  Server tcp port (default: 8000)
  -H HOST, --host HOST  Host to listen on, Ex. 0.0.0.0 (default: localhost)
```

Sample API Usage
----------------

You can use it like this:

```shell
curl http://localhost:8000/v1/audio/speech -H "Content-Type: application/json" -d '{
    "model": "tts-1",
    "input": "The quick brown fox jumped over the lazy dog.",
    "voice": "alloy",
    "response_format": "mp3",
    "speed": 1.0
  }' > speech.mp3
```

Or just like this:

```shell
curl http://localhost:8000/v1/audio/speech -H "Content-Type: application/json" -d '{
    "input": "The quick brown fox jumped over the lazy dog."}' > speech.mp3
```

Or like this example from the [OpenAI Text to speech guide](https://platform.openai.com/docs/guides/text-to-speech):

```python
import openai

client = openai.OpenAI(
  # This part is not needed if you set these environment variables before import openai
  # export OPENAI_API_KEY=sk-11111111111
  # export OPENAI_BASE_URL=http://localhost:8000/v1
  api_key = "sk-111111111",
  base_url = "http://localhost:8000/v1",
)

with client.audio.speech.with_streaming_response.create(
  model="tts-1",
  voice="alloy",
  input="Today is a wonderful day to build something people love!"
) as response:
  response.stream_to_file("speech.mp3")
```

Or if using [open-webui](https://github.com/open-webui/open-webui) as a local LLM frontend for Ollama, when both are running on your PC:

1. Start the `open-webui` docker container [as per their instructions](https://github.com/open-webui/open-webui?tab=readme-ov-file#quick-start-with-docker-)

2. Open your web browser to http://localhost:3000/

3. Go to *Profile -> Settings -> Audio*

4. Set the *API Base URL* to `http://host.docker.internal:8000/v1`. This allows `open-webui` access to `localhost` on your PC from inside the Docker container.

5. Set *API Key* to `sk-111111111`.

6. Click *Save*

7. Click the *Read Aloud* below any response during a chat session to hear the response.

Also see the `say.py` sample application for an example of how to use the openai-python API.

```
$ python say.py -i "The quick brown fox jumped over the lazy dog." -p # play the audio, requires 'pip install playsound'
$ python say.py -i "The quick brown fox jumped over the lazy dog." -m tts-1-hd -v onyx -f flac -o fox.flac # save to a file.
```


Custom Voices Howto
-------------------

Custom voices should be mono 22050 hz sample rate WAV files with low noise (no background music, etc.) and not contain any partial words.Sample voices for xtts should be at least 6 seconds long, but they can be longer. However, longer samples do not always produce better results.

You can use FFmpeg to process your audio files and prepare them for xtts, here are some examples:

```shell
# convert a multi-channel audio file to mono, set sample rate to 22050 hz, trim to 6 seconds, and output as WAV file.
ffmpeg -i input.mp3 -ac 1 -ar 22050 -t 6 -y me.wav
# use a simple noise filter to clean up audio, and select a start time start for sampling.
ffmpeg -i input.wav -af "highpass=f=200, lowpass=f=3000" -ac 1 -ar 22050 -ss 00:13:26.2 -t 6 -y me.wav
# A more complex noise reduction setup, including volume adjustment
ffmpeg -i input.mkv -af "highpass=f=200, lowpass=f=3000, volume=5, afftdn=nf=25" -ac 1 -ar 22050 -ss 00:13:26.2 -t 6 -y me.wav
```

Once your WAV file is prepared, save it in the `/voices/` directory and update the `voice_to_speaker.yaml` file with the new file name.

For example:

```yaml
...
tts-1-hd:
  me:
    model: xtts_v2.0.2 # you can specify different xtts versions
    speaker: voices/me.wav # this could be you
```
