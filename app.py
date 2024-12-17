from flask import Flask, request, render_template, jsonify
from pytubefix.cli import YouTube
from pytube.exceptions import RegexMatchError
from moviepy.video.io.ffmpeg_tools import ffmpeg_extract_audio
import ssl
import certifi
import os
import threading
import time
import uuid  # To generate unique IDs for downloads

# Fix for HTTP 403 Error
ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

app = Flask(__name__)

# Global variable to store download progress
progress_data = {}

# Set the default save folder
DEFAULT_SAVE_FOLDER = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DEFAULT_SAVE_FOLDER):
    os.makedirs(DEFAULT_SAVE_FOLDER)

# Progress callback
def on_progress(stream, chunk, bytes_remaining, download_id):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    percentage = int((bytes_downloaded / total_size) * 100)
    progress_data[download_id] = percentage

# Function to convert video to MP3
def convert_to_mp3(file_path):
    base, ext = os.path.splitext(file_path)
    mp3_path = base + ".mp3"
    ffmpeg_extract_audio(file_path, mp3_path)
    os.remove(file_path)
    return mp3_path

# Function to download video/audio
def download_video(url, file_type, save_path, download_id):
    try:
        yt = YouTube(url, on_progress_callback=lambda s, c, b: on_progress(s, c, b, download_id))
        if file_type == "MP4":
            stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        elif file_type == "MP3":
            stream = yt.streams.filter(only_audio=True).first()
        else:
            progress_data[download_id] = "error"
            return {"status": "error", "message": "Invalid file type selected"}

        if not stream:
            progress_data[download_id] = "error"
            return {"status": "error", "message": "No valid stream found"}

        file_path = stream.download(save_path)
        if file_type == "MP3":
            file_path = convert_to_mp3(file_path)

        progress_data[download_id] = "complete"
        return {"status": "success", "file_path": file_path}
    except RegexMatchError:
        progress_data[download_id] = "error"
        return {"status": "error", "message": "Invalid YouTube URL"}
    except Exception as e:
        progress_data[download_id] = "error"
        return {"status": "error", "message": str(e)}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        url = request.form.get('url')
        file_type = request.form.get('file_type')
        download_id = str(uuid.uuid4())  # Generate unique ID for progress tracking
        save_path = DEFAULT_SAVE_FOLDER

        # Initialize progress
        progress_data[download_id] = 0

        # Start download in a separate thread
        threading.Thread(target=download_video, args=(url, file_type, save_path, download_id)).start()
        return render_template("index.html", download_id=download_id)

    return render_template("index.html")

@app.route('/progress/<download_id>', methods=['GET'])
def progress(download_id):
    progress = progress_data.get(download_id, 0)
    return jsonify({"progress": progress})

if __name__ == '__main__':
    app.run(debug=True)
