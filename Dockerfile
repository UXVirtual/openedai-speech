FROM python:3.11-slim

ENV COQUI_TOS_AGREED=1
#ENV PRELOAD_MODEL=xtts
ENV PRELOAD_MODEL=parler-tts/parler_tts_mini_v0.1

RUN apt-get update && \
    apt-get install --no-install-recommends -y build-essential cargo g++ gcc curl git ffmpeg
RUN apt-get update
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN cargo --help
#RUN git clone https://github.com/matatonic/openedai-speech /app
RUN mkdir -p /app/voices
#default clone of the default voice is really bad, use a better default
COPY voices/alloy-alt.wav /app/voices/
WORKDIR /app
COPY *.txt /app/
RUN pip install --no-cache -r requirements.txt
COPY *.sh /app/
RUN ./download_voices_tts-1.sh
RUN ./download_voices_tts-1-hd.sh
COPY *.py *.yaml *.md LICENSE /app/

RUN apt-get clean && rm -rf /var/lib/apt/lists/*

#standard method of starting speech service
#CMD python speech.py --host 0.0.0.0 --port 8000 --preload $PRELOAD_MODEL

#alternate method for macbook pro m1 mps device - specify mps device to be used for apple silicon
CMD python speech.py --host 0.0.0.0 --port 8000 --xtts_device "mps:0" --preload $PRELOAD_MODEL
