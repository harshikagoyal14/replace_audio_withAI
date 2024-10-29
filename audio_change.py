import streamlit as st
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
import librosa
from pydub import AudioSegment
import moviepy.editor as mp
from google.cloud import speech, texttospeech
import openai
import os
from google.oauth2 import service_account
import soundfile as sf
import numpy as np

# Set up Google Cloud credentials and environment variables
credentials = service_account.Credentials.from_service_account_info(st.secrets["google_cloud"])

# Streamlit app title
st.title("Video Transcription and Audio Replacement with Synchronization")

# Streamlit video file uploader
uploaded_video = st.file_uploader("Upload a Video", type=["mp4"])

# Function to split audio into chunks
def split_audio(file_path, chunk_length_ms=30000):
    audio = AudioSegment.from_wav(file_path).set_channels(1)
    if not os.path.exists("audio_chunks"):
        os.makedirs("audio_chunks")
    chunk_files = []
    for i, chunk in enumerate(audio[::chunk_length_ms]):
        chunk_name = f"audio_chunks/chunk_{i}.wav"
        chunk.export(chunk_name, format="wav")
        chunk_files.append(chunk_name)
    return chunk_files

# Function to extract and transcribe audio
def transcribe_audio_chunked(video_path):
    video = mp.VideoFileClip(video_path)
    video.audio.write_audiofile("extracted_audio.wav")
    chunk_files = split_audio("extracted_audio.wav")
    client = speech.SpeechClient(credentials=credentials)
    full_transcript = ""
    for chunk_file in chunk_files:
        file_size = os.path.getsize(chunk_file)
        if file_size > 10485760:
            raise Exception(f"Audio chunk {chunk_file} exceeds 10 MB size limit")
        with open(chunk_file, "rb") as audio_file:
            content = audio_file.read()
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=44100,
            language_code="en-US",
        )
        response = client.recognize(config=config, audio=audio)
        for result in response.results:
            full_transcript += result.alternatives[0].transcript + " "
    return full_transcript

# GPT-4 correction function
openai.api_type = st.secrets["openai"]["api_type"]
openai.api_key = st.secrets["openai"]["api_key"]
openai.api_base = st.secrets["openai"]["api_base"]
#openai.api_version = st.secrets["openai"]["api_version"]



def correct_transcription(transcript):
    try:
        response = openai.ChatCompletion.create(
            engine="gpt-4o",
            messages=[
                {"role": "system", "content": "Correct grammatical errors and remove filler words."},
                {"role": "user", "content": transcript}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        corrected_transcript = response['choices'][0]['message']['content']
        return corrected_transcript
    except Exception as e:
        st.error(f"Error correcting transcription: {e}")

# Google Cloud Text-to-Speech function
def generate_audio_from_text(corrected_text, credentials):
    client = texttospeech.TextToSpeechClient(credentials=credentials)
    input_text = texttospeech.SynthesisInput(text=corrected_text)
    voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Standard-C")
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    response = client.synthesize_speech(input=input_text, voice=voice, audio_config=audio_config)
    with open("corrected_audio.mp3", "wb") as out:
        out.write(response.audio_content)
    return "corrected_audio.mp3"

# Replace audio in video function
def replace_audio_in_video(video_path, audio_path, output_path):
    video = mp.VideoFileClip(video_path)
    audio = mp.AudioFileClip(audio_path)
    final_video = video.set_audio(audio)
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac")

# Function to align corrected audio to original using DTW
def align_audio_dtw(original_audio_path, new_audio_path):
    # Load the original and new audio files
    original_audio, sr_orig = librosa.load(original_audio_path, sr=None)
    new_audio, sr_new = librosa.load(new_audio_path, sr=None)

    # Extract MFCC features for both audio signals
    mfcc_orig = librosa.feature.mfcc(y=original_audio, sr=sr_orig, n_mfcc=13)
    mfcc_new = librosa.feature.mfcc(y=new_audio, sr=sr_new, n_mfcc=13)

    # Perform DTW alignment
    distance, path = fastdtw(mfcc_orig.T, mfcc_new.T, dist=euclidean)

    # Resample new audio to match the timing of the original audio
    aligned_audio = librosa.resample(new_audio, orig_sr=sr_new, target_sr=sr_orig)
    aligned_audio_path = "aligned_corrected_audio.wav"
    sf.write(aligned_audio_path, aligned_audio, sr_orig)

    return aligned_audio_path

# Streamlit button to process the uploaded video
if uploaded_video is not None:
    video_path = uploaded_video.name
    with open(video_path, "wb") as f:
        f.write(uploaded_video.getbuffer())

    # Step 1: Transcribe video audio
    st.write("Transcribing audio...")
    transcript = transcribe_audio_chunked(video_path)
    st.write("Original Transcript:", transcript)

    # Step 2: Correct the transcription
    st.write("Correcting transcription...")
    corrected_transcript = correct_transcription(transcript)
    st.write("Corrected Transcript:", corrected_transcript)

    # Step 3: Generate corrected audio
    st.write("Generating corrected audio...")
    corrected_audio_path = generate_audio_from_text(corrected_transcript, credentials)

    # Step 4: Align corrected audio to original video using DTW
    st.write("Aligning corrected audio with the original video...")
    aligned_audio_path = align_audio_dtw("extracted_audio.wav", corrected_audio_path)

    # Step 5: Replace audio in the video
    st.write("Replacing audio in the video...")
    output_video_path = 'output_video.mp4'
    replace_audio_in_video(video_path, aligned_audio_path, output_video_path)

    st.write("Process completed! You can download the final video below.")
    with open(output_video_path, "rb") as f:
        st.download_button("Download Final Video", f, file_name="final_video.mp4")
