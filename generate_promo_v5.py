import os
import platform
import gc

# Patch platform.win32_ver for Python 3.13 compatibility
if not hasattr(platform, 'win32_ver') or platform.win32_ver.__code__.co_argcount == 0:
    def fixed_win32_ver(version='', csd='', ptype=''):
        return '10', '10.0.19041', 'SP0', 'Multiprocessor Free'
    platform.win32_ver = fixed_win32_ver

# Force FFmpeg path
ffmpeg_path = r"D:\karaj\garage_manager_project\garage_manager\.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
if os.path.exists(ffmpeg_path):
    os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path

import random
from moviepy import *
from moviepy.video.fx import Resize
from moviepy.audio.io.AudioFileClip import AudioFileClip

# Configuration
OUTPUT_FILE = "static/video/promo_v5_with_sound.mp4"
IMAGE_DIR = "static/video"
AUDIO_DIR = "static/audio"
DURATION_INTRO = 3
DURATION_SLIDE = 4
RESOLUTION = (640, 360) 
FPS = 24
FONT = "arial.ttf"
if not os.path.exists(FONT):
    FONT = "C:/Windows/Fonts/arial.ttf"

def get_audio(name, duration):
    path = os.path.join(AUDIO_DIR, f"{name}.mp3")
    if os.path.exists(path):
        try:
            return AudioFileClip(path, buffersize=20000)
        except Exception as e:
            print(f"Failed to load audio {name}: {e}")
    return None

def create_text_clip_obj(text, fontsize, color, duration, audio_name=None, position="center"):
    txt = TextClip(
        text=text,
        font_size=fontsize,
        color=color,
        font=FONT,
        size=RESOLUTION,
        method="caption",
        text_align="center"
    ).with_duration(duration).with_position(position)
    
    if audio_name:
        audio = get_audio(audio_name, duration)
        if audio:
            txt = txt.with_audio(audio)
    return txt

def create_image_slide_obj(image_path, text, duration, audio_name=None):
    img = ImageClip(image_path).with_duration(duration)
    img_w, img_h = img.size
    target_w, target_h = RESOLUTION
    scale = max(target_w / img_w, target_h / img_h)
    img = img.with_effects([Resize(scale)])
    
    txt = TextClip(
        text=text,
        font_size=50,
        color="white",
        font=FONT,
        stroke_color="black",
        stroke_width=2,
        method="caption",
        size=(RESOLUTION[0], 100),
        text_align="center"
    ).with_position(("center", "bottom")).with_duration(duration)
    
    comp = CompositeVideoClip([img, txt], size=RESOLUTION)
    if audio_name:
        audio = get_audio(audio_name, duration)
        if audio:
            comp = comp.with_audio(audio)
    return comp

def render_single_clip(clip, filename):
    print(f"Rendering {filename}...")
    clip.write_videofile(filename, fps=FPS, codec="libx264", audio_codec="aac", threads=1, preset="ultrafast", logger=None)
    clip.close()
    if clip.audio:
        clip.audio.close()
    gc.collect()
    return filename

def main():
    print("Generating Promo Video V5 (Serial Mode)...")
    temp_files = []
    
    try:
        # Intro
        print("Processing Intro...")
        c1 = create_text_clip_obj("Azad Company Presents", 70, "#FFD700", DURATION_INTRO, "intro1")
        temp_files.append(render_single_clip(c1, "temp_01.mp4"))
        
        c2 = create_text_clip_obj("A Masterpiece by\nMaster User Azad", 70, "#FFFFFF", DURATION_INTRO, "intro2")
        temp_files.append(render_single_clip(c2, "temp_02.mp4"))
        
        c3 = create_text_clip_obj("GANGS OF PALESTINE", 90, "#FF0000", DURATION_INTRO + 1, "intro3")
        temp_files.append(render_single_clip(c3, "temp_03.mp4"))

        # Gameplay
        print("Processing Gameplay...")
        all_files = sorted([f for f in os.listdir(IMAGE_DIR) if f.startswith("shot_") and f.endswith(".png")])
        english_shots = [f for f in all_files if "ar_" not in f]
        arabic_shots = [f for f in all_files if "ar_" in f]

        slides_config = [
            ("hara", "Explore the Streets", "slide1"),
            ("gym", "Train for Power", "slide2"),
            ("market", "Dominate the Economy", "slide3"),
            ("bank", "Manage Your Wealth", "slide4"),
            ("garage", "Ride in Style", "slide5"),
            ("casino", "High Stakes Gambling", "slide6"),
            ("hostess", "Luxury Lifestyle", "slide7"),
            ("fight", "Brutal Combat", "slide8"),
            ("investigation", "Gather Intel", "slide9"),
            ("admin", "Total Control", "slide10"),
        ]

        idx = 4
        for keyword, text, audio_name in slides_config:
            # Find image
            img_path = None
            for s in english_shots:
                if keyword in s:
                    img_path = os.path.join(IMAGE_DIR, s)
                    break
            if not img_path and english_shots:
                img_path = os.path.join(IMAGE_DIR, random.choice(english_shots))
            
            if img_path:
                clip = create_image_slide_obj(img_path, text, DURATION_SLIDE, audio_name)
                temp_files.append(render_single_clip(clip, f"temp_{idx:02d}.mp4"))
                idx += 1

        # Arabic Transition
        c_trans = create_text_clip_obj("Full Arabic Localization", 60, "#00FF00", 3, "trans1")
        temp_files.append(render_single_clip(c_trans, f"temp_{idx:02d}.mp4"))
        idx += 1

        # Arabic Slides
        arabic_keywords = ["hara", "market", "garage", "developer"]
        first_ar = True
        for kw in arabic_keywords:
            img_path = None
            for s in arabic_shots:
                if kw in s:
                    img_path = os.path.join(IMAGE_DIR, s)
                    break
            if not img_path and arabic_shots:
                img_path = os.path.join(IMAGE_DIR, random.choice(arabic_shots))
                
            if img_path:
                audio = "trans2" if first_ar else None
                clip = create_image_slide_obj(img_path, "تجربة عربية كاملة", 3, audio)
                temp_files.append(render_single_clip(clip, f"temp_{idx:02d}.mp4"))
                idx += 1
                first_ar = False

        # Outro
        print("Processing Outro...")
        out1 = create_text_clip_obj("Join the Gang", 80, "#FF0000", 3, "outro1")
        temp_files.append(render_single_clip(out1, f"temp_{idx:02d}.mp4"))
        idx += 1
        
        out2 = create_text_clip_obj("Play Now at\nlocalhost:8000", 60, "#FFFFFF", 4, "outro2")
        temp_files.append(render_single_clip(out2, f"temp_{idx:02d}.mp4"))
        idx += 1
        
        out3 = create_text_clip_obj("Azad Company", 50, "#FFD700", 3, "outro3")
        temp_files.append(render_single_clip(out3, f"temp_{idx:02d}.mp4"))
        idx += 1

        # Concatenate All
        print("Concatenating all segments...")
        clips = [VideoFileClip(f) for f in temp_files]
        final = concatenate_videoclips(clips)
        final.write_videofile(OUTPUT_FILE, fps=FPS, codec="libx264", audio_codec="aac", threads=1, preset="ultrafast")
        final.close()
        for c in clips: c.close()

        print(f"Success! Video saved to {OUTPUT_FILE}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup temp files
        print("Cleaning up temp files...")
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass

if __name__ == "__main__":
    main()
