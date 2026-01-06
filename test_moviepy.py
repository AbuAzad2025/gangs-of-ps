import platform
# Patch platform.win32_ver for Python 3.13 compatibility
if not hasattr(platform, 'win32_ver') or platform.win32_ver.__code__.co_argcount == 0:
    def fixed_win32_ver(version='', csd='', ptype=''):
        return '10', '10.0.19041', 'SP0', 'Multiprocessor Free'
    platform.win32_ver = fixed_win32_ver

import os
# Force FFmpeg path
ffmpeg_path = r"D:\karaj\garage_manager_project\garage_manager\.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
if os.path.exists(ffmpeg_path):
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path

from moviepy import *
from moviepy.audio.io.AudioFileClip import AudioFileClip

try:
    print("Testing AudioFileClip with small buffer...")
    audio_path = "static/audio/intro1.mp3"
    if os.path.exists(audio_path):
        # Try reducing buffersize
        audioclip = AudioFileClip(audio_path, buffersize=20000)
        print(f"Loaded {audio_path}, duration: {audioclip.duration}")
        # Try reading a chunk
        chunk = audioclip.get_frame(0)
        print(f"Read chunk shape: {chunk.shape}")
        audioclip.close()
        print("Closed.")
    else:
        print("Audio file not found.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
