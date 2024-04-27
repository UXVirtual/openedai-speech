#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import tempfile
import yaml
from fastapi.responses import StreamingResponse
import uvicorn
from pydantic import BaseModel

# for parler
try:
    from parler_tts import ParlerTTSForConditionalGeneration
    from transformers import AutoTokenizer, logging
    import torch
    import soundfile as sf
    logging.set_verbosity_error()
    has_parler_tts = True
except ImportError:
    print("No parler support found")
    has_parler_tts = False

import openedai

xtts = None
args = None
app = openedai.OpenAIStub()

class xtts_wrapper():
    def __init__(self, model_name, device):
        self.model_name = model_name
        self.xtts = TTS(model_name=model_name, progress_bar=False).to(device)

    def tts(self, text, speaker_wav, speed):
        tf, file_path = tempfile.mkstemp(suffix='.wav')

        file_path = self.xtts.tts_to_file(
            text,
            language='en',
            speaker_wav=speaker_wav,
            speed=speed,
            file_path=file_path,
        )

        os.unlink(file_path)
        return tf

class parler_tts():
    def __init__(self, model_name, device):
        self.model_name = model_name
        self.model = ParlerTTSForConditionalGeneration.from_pretrained(model_name).to(device)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def tts(self, text, description):
        input_ids = self.tokenizer(description, return_tensors="pt").input_ids.to(self.model.device)
        prompt_input_ids = self.tokenizer(text, return_tensors="pt").input_ids.to(self.model.device)

        generation = self.model.generate(input_ids=input_ids, prompt_input_ids=prompt_input_ids)
        audio_arr = generation.cpu().numpy().squeeze()
        
        tf, file_path = tempfile.mkstemp(suffix='.wav')
        sf.write(file_path, audio_arr, self.model.config.sampling_rate)
        os.unlink(file_path)
        return tf


# Read pre process map on demand so it can be changed without restarting the server
def preprocess(raw_input):
    with open('pre_process_map.yaml', 'r', encoding='utf8') as file:
        pre_process_map = yaml.safe_load(file)
        for a, b in pre_process_map:
            raw_input = re.sub(a, b, raw_input)
    return raw_input

# Read voice map on demand so it can be changed without restarting the server
def map_voice_to_speaker(voice: str, model: str):
    with open('voice_to_speaker.yaml', 'r', encoding='utf8') as file:
        voice_map = yaml.safe_load(file)
        return voice_map[model][voice]['model'], voice_map[model][voice]['speaker'], 

class GenerateSpeechRequest(BaseModel):
    model: str = "tts-1" # or "tts-1-hd"
    input: str
    voice: str = "alloy"  # alloy, echo, fable, onyx, nova, and shimmer
    response_format: str = "mp3" # mp3, opus, aac, flac, wav
    speed: float = 1.0 # 0.25 - 4.0

def build_ffmpeg_args(response_format, input_format, sample_rate):
    # Convert the output to the desired format using ffmpeg
    if input_format == 'raw':
        ffmpeg_args = ["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", sample_rate, "-ac", "1", "-i", "-"]
    else:
        ffmpeg_args = ["ffmpeg", "-loglevel", "error", "-f", "WAV", "-i", "-"]

    if response_format == "mp3":
        ffmpeg_args.extend(["-f", "mp3", "-c:a", "libmp3lame", "-ab", "64k"])
    elif response_format == "opus":
        ffmpeg_args.extend(["-f", "ogg", "-c:a", "libopus"])
    elif response_format == "aac":
        ffmpeg_args.extend(["-f", "adts", "-c:a", "aac", "-ab", "64k"])
    elif response_format == "flac":
        ffmpeg_args.extend(["-f", "flac", "-c:a", "flac"])

    return ffmpeg_args

@app.post("/v1/audio/speech", response_class=StreamingResponse)
async def generate_speech(request: GenerateSpeechRequest):
    global xtts, args
    input_text = preprocess(request.input)
    model = request.model
    voice = request.voice
    response_format = request.response_format
    speed = request.speed

    # Set the Content-Type header based on the requested format
    if response_format == "mp3":
        media_type = "audio/mpeg"
    elif response_format == "opus":
        media_type = "audio/ogg;codecs=opus"
    elif response_format == "aac":
        media_type = "audio/aac"
    elif response_format == "flac":
        media_type = "audio/x-flac"
    elif response_format == "wav":
        media_type = "audio/wav"

    ffmpeg_args = None
    tts_io_out = None

    # Use piper for tts-1, and if xtts_device == none use for all models.
    if model == 'tts-1' or args.xtts_device == 'none':
        piper_model, speaker = map_voice_to_speaker(voice, 'tts-1')
        if(response_format == "wav"):
            tts_args = ["piper", "--model", str(piper_model), "--data-dir", "voices", "--download-dir", "voices"]
        else:
            tts_args = ["piper", "--model", str(piper_model), "--data-dir", "voices", "--download-dir", "voices", "--output-raw"]

        if args.piper_cuda:
            tts_args.extend(["--cuda"])
        if speaker:
            tts_args.extend(["--speaker", str(speaker)])
        if speed != 1.0:
            tts_args.extend(["--length-scale", f"{1.0/speed}"])

        tts_proc = subprocess.Popen(tts_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        tts_proc.stdin.write(bytearray(input_text.encode('utf-8')))
        tts_proc.stdin.close()
        tts_io_out = tts_proc.stdout
        ffmpeg_args = build_ffmpeg_args(response_format, input_format="raw", sample_rate="22050")

    # Use xtts for tts-1-hd
    elif model == 'tts-1-hd':
        tts_model, speaker = map_voice_to_speaker(voice, 'tts-1-hd')

        if xtts is not None and xtts.model_name != tts_model:
            import torch, gc
            del xtts
            xtts = None
            gc.collect()
            torch.cuda.empty_cache()

        if 'parler-tts' in tts_model and has_parler_tts:
            if xtts is None:
                xtts = parler_tts(tts_model, device=args.xtts_device)

            ffmpeg_args = build_ffmpeg_args(response_format, input_format="WAV", sample_rate=str(xtts.model.config.sampling_rate))

            if speed != 1:
                ffmpeg_args.extend(["-af", f"atempo={speed}"]) 

            tts_io_out = xtts.tts(text=input_text, description=speaker)

        else:
            if xtts is None:
                xtts = xtts_wrapper(tts_model, device=args.xtts_device)

            ffmpeg_args = build_ffmpeg_args(response_format, input_format="WAV", sample_rate="24000")

            # tts speed doesn't seem to work well
            if speed < 0.5:
                speed = speed / 0.5
                ffmpeg_args.extend(["-af", "atempo=0.5"]) 
            if speed > 1.0:
                ffmpeg_args.extend(["-af", f"atempo={speed}"]) 
                speed = 1.0

            tts_io_out = xtts.tts(text=input_text, speaker_wav=speaker, speed=speed)

    if(response_format == "wav"):
        # Send the TTS wav output
        return StreamingResponse(content=tts_io_out, media_type=media_type)
    else:
        # Pipe the output from piper/xtts to the input of ffmpeg
        ffmpeg_args.extend(["-"])
        ffmpeg_proc = subprocess.Popen(ffmpeg_args, stdin=tts_io_out, stdout=subprocess.PIPE)

        return StreamingResponse(content=ffmpeg_proc.stdout, media_type=media_type)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='OpenedAI Speech API Server',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--piper_cuda', action='store_true', default=False, help="Enable cuda for piper. Note: --cuda/onnxruntime-gpu is not working for me, but cpu is fast enough") 
    parser.add_argument('--xtts_device', action='store', default="cuda", help="Set the device for the xtts model. The special value of 'none' will use piper for all models.")
    parser.add_argument('--preload', action='store', default=None, help="Preload a model (Ex. 'xtts' or 'xtts_v2.0.2'). By default it's loaded on first use.")
    parser.add_argument('-P', '--port', action='store', default=8000, type=int, help="Server tcp port")
    parser.add_argument('-H', '--host', action='store', default='localhost', help="Host to listen on, Ex. 0.0.0.0")

    args = parser.parse_args()

    if args.xtts_device != "none":
        from TTS.api import TTS

    if args.preload:
        if 'parler-tts' in args.preload:
            xtts = parler_tts(args.preload, device=args.xtts_device)
        else:
            xtts = xtts_wrapper(args.preload, device=args.xtts_device)

    app.register_model('tts-1')
    app.register_model('tts-1-hd')

    uvicorn.run(app, host=args.host, port=args.port)
