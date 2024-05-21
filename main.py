import asyncio
import sounddevice as sd
import boto3
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

class MyEventHandler(TranscriptResultStreamHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.full_transcript = []
        self.previous_transcript = ""

    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            for alt in result.alternatives:
                new_transcript = alt.transcript.strip()
                if new_transcript and new_transcript != self.previous_transcript:
                    self.full_transcript.append(new_transcript)
                    self.previous_transcript = new_transcript

    def save_transcript_to_file(self, filename):
        with open(filename, "w", encoding="utf-8") as f:
            f.write(" ".join(self.full_transcript))

    def get_unique_transcript(self):
        full_text = " ".join(self.full_transcript)
        unique_words = set(full_text.split())
        unique_transcript = sorted(unique_words)
        unique_transcript_joined = " ".join(unique_transcript)
        unique_transcript_final = " ".join(unique_transcript_joined.split())
        return unique_transcript_final

    def save_last_transcript_to_file(self, filename):
        if self.full_transcript:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(self.full_transcript[-1])

async def mic_stream(duration):
    loop = asyncio.get_event_loop()
    input_queue = asyncio.Queue()

    def callback(indata, frame_count, time_info, status):
        loop.call_soon_threadsafe(input_queue.put_nowait, (bytes(indata), status))

    stream = sd.RawInputStream(
        channels=1,
        samplerate=16000,
        callback=callback,
        blocksize=1024 * 2,
        dtype="int16",
    )

    with stream:
        start_time = loop.time()
        while loop.time() - start_time < duration:
            indata, status = await input_queue.get()
            yield indata, status

async def write_chunks(stream, duration):
    async for chunk, status in mic_stream(duration):
        await stream.input_stream.send_audio_event(audio_chunk=chunk)
    await stream.input_stream.end_stream()

async def basic_transcribe():
    client = TranscribeStreamingClient(region="us-west-2")

    stream = await client.start_stream_transcription(
        language_code="es-US",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )

    handler = MyEventHandler(stream.output_stream)
    await asyncio.gather(write_chunks(stream, 10), handler.handle_events())#on this line, 10 seconds, you decide change to other value


    handler.save_last_transcript_to_file("last_transcript.txt")

    print("Transcripción completa:")
    print(handler.full_transcript[-1])

    polly = boto3.client('polly', region_name='us-west-2')
    response = polly.synthesize_speech(
        Text=handler.full_transcript[-1],
        OutputFormat='mp3',
        VoiceId='Lucia'  
    )

    if 'AudioStream' in response:
        with open('transcript.mp3', 'wb') as file:
            file.write(response['AudioStream'].read())

if __name__ == "__main__":
    asyncio.run(basic_transcribe())

    

