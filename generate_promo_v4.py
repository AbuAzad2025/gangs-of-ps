from moviepy import *
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Config
WIDTH, HEIGHT = 1280, 720
DURATION_PER_SLIDE = 4
OUTPUT_PATH = "static/video/promo_v4.mp4"
FONT_PATH = "static/fonts/ReemKufi-Regular.ttf"  # Assuming this exists, otherwise default

def create_text_clip(text, fontsize=70, color='white', duration=2):
    # Create text image using PIL
    img = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Load font
    try:
        font = ImageFont.truetype("arial.ttf", fontsize) # Try system font first for English
    except:
        font = ImageFont.load_default()

    # Draw text centered
    # Get bounding box
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    
    x = (WIDTH - text_width) // 2
    y = (HEIGHT - text_height) // 2
    
    # Shadow
    draw.text((x+4, y+4), text, font=font, fill='black')
    # Text
    draw.text((x, y), text, font=font, fill=color)
    
    return ImageClip(np.array(img)).with_duration(duration)

def create_slide(image_path, text, subtext):
    if not os.path.exists(image_path):
        print(f"Warning: {image_path} not found")
        return None

    # Load image
    clip = ImageClip(image_path).resized(width=WIDTH) # Resize to fit width
    
    # Center vertically if needed
    if clip.h < HEIGHT:
        # Pad?
        clip = clip.on_color(size=(WIDTH, HEIGHT), color=(0,0,0))
    elif clip.h > HEIGHT:
        # Crop center
        clip = clip.cropped(y1=(clip.h-HEIGHT)//2, height=HEIGHT)
    
    clip = clip.with_duration(DURATION_PER_SLIDE)

    # Add Zoom effect (manual scale implementation or just simple static)
    # MoviePy 2.x doesn't have easy zoom, let's stick to static for stability
    
    # Create Text Overlay
    txt_clip = create_text_clip(text, fontsize=80, color='#FFD700', duration=DURATION_PER_SLIDE)
    sub_clip = create_text_clip(subtext, fontsize=40, color='white', duration=DURATION_PER_SLIDE)
    
    # Position text
    txt_clip = txt_clip.with_position(('center', 'center'))
    sub_clip = sub_clip.with_position(('center', HEIGHT//2 + 60))
    
    return CompositeVideoClip([clip, txt_clip, sub_clip])

def main():
    print("Generating Promo V4...")
    
    clips = []
    
    # Slide 1: Hara
    clip1 = create_slide("static/video/shot_hara.png", "Control The Streets", "Manage your empire from the Hara")
    if clip1: clips.append(clip1)
    
    # Slide 2: Market
    clip2 = create_slide("static/video/shot_market.png", "Black Market", "Trade weapons, drugs, and rare items")
    if clip2: clips.append(clip2)
    
    # Slide 3: Gangs
    clip3 = create_slide("static/video/shot_gangs.png", "Join a Gang", "Fight together, rule together")
    if clip3: clips.append(clip3)
    
    # Final
    final_text = create_text_clip("Gangs of Palestine", fontsize=100, color='#FFD700', duration=3)
    final_bg = ColorClip(size=(WIDTH, HEIGHT), color=(0,0,0), duration=3)
    final = CompositeVideoClip([final_bg, final_text])
    clips.append(final)
    
    # Concatenate
    video = concatenate_videoclips(clips)
    
    # Write
    video.write_videofile(OUTPUT_PATH, fps=24)
    print(f"Video saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    import numpy as np # Needed for PIL conversion
    main()
