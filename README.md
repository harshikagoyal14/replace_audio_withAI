# Video Transcription and Audio Replacement with Synchronization

This is a Streamlit-based web application that allows users to upload a video, transcribe its audio, correct the transcription using GPT-4, generate a new audio file, and synchronize the new audio with the original video using Dynamic Time Warping (DTW). The app leverages Google Cloud's Speech-to-Text and Text-to-Speech APIs.

## Features
- Upload video files.
- Extract and transcribe audio using Google Cloud's Speech-to-Text.
- Correct the transcription using GPT-4.
- Generate new audio from the corrected transcription using Google Cloud's Text-to-Speech.
- Synchronize the corrected audio with the original video using DTW (Dynamic Time Warping).
- Replace the original video audio with the corrected synchronized audio.

## Technologies Used
- **Streamlit**: Web interface for uploading videos and displaying results.
- **Google Cloud APIs**: Speech-to-Text and Text-to-Speech.
- **OpenAI**: GPT-4 for transcription correction.
- **Pydub**: Audio processing and splitting.
- **MoviePy**: Video processing and manipulation.
- **FastDTW & SciPy**: For dynamic time warping to align audio tracks.
- **Librosa**: Audio feature extraction and resampling.
- **SoundFile**: For saving audio files.

## Installation

### 1. Clone the Repository
   
    git clone https://github.com/your-username/your-repository.git
    cd your-repository

### 2. Install Dependencies
You need to install the required Python packages. You can use the requirements.txt to install them:

    
    pip install -r requirements.txt


### 3. Set Up Google Cloud Credentials
To use Google Cloud's Speech-to-Text and Text-to-Speech APIs, you'll need a Google Cloud project and a service account key.

##### 1. Go to the Google Cloud Console.
##### 2. Create a new project and enable the Speech-to-Text and Text-to-Speech APIs.
##### 3. Create a service account key and download the JSON file.
##### 4. Store the JSON file in the app as a secret for Streamlit Cloud, or if running locally, use environment variables.

In your .streamlit/secrets.toml (for Streamlit Cloud) or environment variables (for local), add the following:    

    [google_cloud]
    api_key = "your-google-cloud-api-key"
    service_account_info = { ... }  # JSON credentials for     service account

    [openai]
    api_key = "your-openai-api-key"
    api_base = "https://api.openai.com/"
    api_version = "v1"

### 4. Run the application locally :
    streamlit run app.py


## Usage:

#### 1. Upload a video file (MP4).
#### 2. The app will automatically extract and transcribe the audio.
#### 3. GPT-4 will correct the transcription.
#### 4. Google Cloud's Text-to-Speech will generate a new audio file from the corrected transcript.
#### 5. The app will align the new audio with the original video using DTW.
#### 6. The final video with the corrected and aligned audio will be available for download.

