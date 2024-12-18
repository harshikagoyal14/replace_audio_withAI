import streamlit as st
from fastdtw import fastdtw
from scipy.spatial.distance import euclidean
import librosa
from pydub import AudioSegment
import moviepy.editor as mp
from google.cloud import speech, texttospeech
import google.generativeai as genai
import os
from google.oauth2 import service_account
import soundfile as sf
import numpy as np

# Set up Google Cloud credentials and environment variables
credentials = service_account.Credentials.from_service_account_info(st.secrets["google_cloud"])
GOOGLE_API_KEY = st.secrets["google_api"]["api_key"]

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
        if file_size > 10485760:  # 10 MB limit
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

# Gemini correction function
def correct_transcription(transcript):
    # Configure the API key
    genai.configure(api_key=GOOGLE_API_KEY)

    # Generation configuration settings
    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }

    # Initialize the model
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
    )

    # Start a chat session
    chat_session = model.start_chat(
        history=[
            {
                "role": "user",
                "parts": [
                    {"text": transcript}
                ]
            }
        ]
    )

    # Craft the prompt for correction
    prompt = (
        "Your task is to enhance the provided transcript by correcting any grammatical errors and removing filler words, "
        "such as 'um,' 'uh,' and similar phrases. While making these corrections, it is essential to maintain the original "
        "sentence structure and meaning as closely as possible to avoid any issues with lip syncing. Please ensure that the "
        "revised text reads smoothly while retaining the context of the original speech.\n"
        + transcript
    )

    response = chat_session.send_message(
        {
            "role": "user",
            "parts": [
                {"text": prompt}
            ]
        }
    )

    # Process the response and remove unwanted characters
    corrected_transcript = response.text.replace("*", "").replace("-", "")
    return corrected_transcript

# Google Cloud Text-to-Speech function
def generate_audio_from_text(corrected_text, selected_voice, credentials):
    client = texttospeech.TextToSpeechClient(credentials=credentials)
    input_text = texttospeech.SynthesisInput(text=corrected_text)
    voice = texttospeech.VoiceSelectionParams(
        language_code="en-US" if selected_voice is None else selected_voice,  # Use default if none selected
        name=selected_voice if selected_voice is not None else "en-US-Standard-B"  # Fallback voice if none selected
    )
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

# Function to list available voices with improved descriptions
def list_available_voices(credentials):
    client = texttospeech.TextToSpeechClient(credentials=credentials)
    voices = client.list_voices()
    voice_list = []
    for voice in voices.voices:
        # Improved description format
        voice_info = f"{voice.name} - {voice.ssml_gender} ({', '.join(voice.language_codes)})"
        voice_list.append((voice.name, voice_info))
    return voice_list

# Fetch available voices with improved descriptions
available_voices = list_available_voices(credentials)
voice_options = [voice[1] for voice in available_voices]  # Use the improved descriptions for the selectbox
voice_dict = {voice[1]: voice[0] for voice in available_voices}  # Create a mapping for the selected voice

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

    # Step 3: Voice selection
    st.write("Please select a voice for audio generation:")
    selected_voice_description = st.selectbox("Choose Voice", ["None"] + voice_options)  # Add "None" option
    selected_voice = None if selected_voice_description == "None" else voice_dict[selected_voice_description]  # Get the actual voice name

    # Step 4: Generate corrected audio
    st.write("Generating corrected audio...")
    corrected_audio_path = generate_audio_from_text(corrected_transcript, selected_voice, credentials)

    # Step 5: Align corrected audio to original video using DTW
    st.write("Aligning corrected audio with the original video...")
    aligned_audio_path = align_audio_dtw("extracted_audio.wav", corrected_audio_path)

    # Step 6: Replace audio in the video
    st.write("Replacing audio in the video...")
    output_video_path = 'output_video.mp4'
    replace_audio_in_video(video_path, aligned_audio_path, output_video_path)

    st.write("Process completed! You can download the final video below.")
    with open(output_video_path, "rb") as f:
        st.download_button("Download Final Video", f, file_name="final_video.mp4")
