from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from dotenv import load_dotenv
import random
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
CORS(app)  # Allow CORS so the React frontend can make requests

# Retrieve the API key from environment variables
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Colors for practicing
colors = ["green", "red", "blue", "yellow"]
current_color = None
user_state = {
    "current_color": None,
    "last_response": None,
    "help_requested": False
}

# Function to generate speech using ElevenLabs client
def generate_speech(text):
    try:
        # Calling the text_to_speech conversion API with detailed parameters
        response = client.text_to_speech.convert(
            voice_id="pNInz6obpgDQGcFmaJgB",  # Adam pre-made voice (replace if desired)
            output_format="mp3_22050_32",
            text=text,
            model_id="eleven_turbo_v2_5",  # Use the turbo model for low latency
            voice_settings=VoiceSettings(
                stability=0.0,
                similarity_boost=1.0,
                style=0.0,
                use_speaker_boost=True,
            ),
        )

        # Generating a unique file name for the output MP3 file
        save_file_path = f"audio_files/{uuid.uuid4()}.mp3"

        # Ensure directory exists
        os.makedirs(os.path.dirname(save_file_path), exist_ok=True)

        # Writing the audio to a file
        with open(save_file_path, "wb") as f:
            for chunk in response:
                if chunk:
                    f.write(chunk)

        print(f"{save_file_path}: A new audio file was saved successfully!")

        # Return the path of the saved audio file
        return save_file_path

    except Exception as e:
        print(f"Error generating speech: {e}")
        return None

# Function to pick a random color
def get_next_color():
    global user_state
    user_state["current_color"] = random.choice(colors)
    return user_state["current_color"]

# Endpoint to start the practice session
@app.route('/start', methods=['POST'])
def start():
    text_prompt = "Would you like to practice colors today?"
    audio_file_path = generate_speech(text_prompt)
    if audio_file_path:
        filename = os.path.basename(audio_file_path)
        return jsonify({"audioUrl": f"/audio/{filename}", "prompt": text_prompt})
    else:
        return jsonify({"error": "Failed to generate audio"}), 500

# Endpoint to handle user response (voice or text)
@app.route('/user-response', methods=['POST'])
def user_response():
    global user_state

    data = request.get_json()
    if not data or 'response' not in data:
        return jsonify({"error": "No response provided"}), 400

    user_response = data['response'].strip().lower()
    user_state["last_response"] = user_response

    if user_response in ["yes", "yes."]:
        current_color = get_next_color()
        text_prompt = f"Great! Let's start with the color {current_color}. Can you show me the sign for {current_color}?"
    elif user_response == "no":
        text_prompt = "Okay, let me know when you're ready to practice!"
    else:
        text_prompt = "I'm sorry, I didn't quite understand that. Would you like to practice colors today?"

    # Generate response audio
    audio_file_path = generate_speech(text_prompt)
    if audio_file_path:
        filename = os.path.basename(audio_file_path)
        return jsonify({"audioUrl": f"/audio/{filename}", "prompt": text_prompt})
    else:
        return jsonify({"error": "Failed to generate audio"}), 500

# Endpoint to provide help or visual clues
@app.route('/help', methods=['POST'])
def provide_help():
    global user_state

    if not user_state["current_color"]:
        return jsonify({"error": "No color is currently being practiced"}), 400

    user_state["help_requested"] = True
    current_color = user_state["current_color"]
    text_prompt = f"No worries! Here's a hint. Watch the video showing the sign for {current_color}."

    # Generate response audio
    audio_file_path = generate_speech(text_prompt)
    if audio_file_path:
        filename = os.path.basename(audio_file_path)
        return jsonify({"audioUrl": f"/audio/{filename}", "prompt": text_prompt, "hintVideoUrl": f"/videos/{current_color}.mp4"})
    else:
        return jsonify({"error": "Failed to generate audio"}), 500

# Endpoint to handle retry after help is provided
@app.route('/retry', methods=['POST'])
def retry():
    global user_state

    if not user_state["current_color"]:
        return jsonify({"error": "No color is currently being practiced"}), 400

    text_prompt = f"Now, give it another try! Show me the sign for {user_state['current_color']}!"
    audio_file_path = generate_speech(text_prompt)
    if audio_file_path:
        filename = os.path.basename(audio_file_path)
        return jsonify({"audioUrl": f"/audio/{filename}", "prompt": text_prompt})
    else:
        return jsonify({"error": "Failed to generate audio"}), 500

# Endpoint to transcribe user audio to text
@app.route('/transcribe-audio', methods=['POST'])
def transcribe_audio():
    if 'file' not in request.files:
        return jsonify({"error": "No audio file uploaded"}), 400

    # Save the uploaded audio file
    audio_file = request.files['file']
    audio_file_path = f"temp_{uuid.uuid4()}.mp3"
    audio_file.save(audio_file_path)

    # Use OpenAI Whisper to transcribe the audio file
    try:
        with open(audio_file_path, "rb") as f:
            transcription = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
            user_response = transcription.text.strip().lower()
            print(f"Transcribed Text: {user_response}")
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return jsonify({"error": "Failed to transcribe audio"}), 500
    finally:
        # Clean up temporary audio file
        if os.path.exists(audio_file_path):
            os.remove(audio_file_path)

    return jsonify({"transcribedText": user_response})

# Route to serve audio files
@app.route('/audio/<path:filename>', methods=['GET'])
def serve_audio(filename):
    from flask import send_from_directory
    audio_directory = os.path.join(os.getcwd(), "audio_files")
    return send_from_directory(audio_directory, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)