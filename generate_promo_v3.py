import os
import random
# MoviePy 2.x imports
from moviepy import ImageClip, ColorClip, CompositeVideoClip, concatenate_videoclips
import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont
import numpy as np

# Configuration
WIDTH, HEIGHT = 1280, 720
FONT_PATH = "C:\\Windows\\Fonts\\arial.ttf" # Standard Windows font
OUTPUT_PATH = "static/video/promo_v3.mp4"

def process_text(text):
    """Reshape Arabic text for correct display"""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

def create_text_clip(text, duration, font_size=70, color='white', bg_color=None):
    """Create a text clip with Arabic support using PIL"""
    # Create an image with PIL
    img_pil = Image.new('RGBA', (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img_pil)
    
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except:
        font = ImageFont.load_default()
    
    # Calculate text size and position
    processed_text = process_text(text)
    
    # Get text bounding box
    left, top, right, bottom = draw.textbbox((0, 0), processed_text, font=font)
    text_w = right - left
    text_h = bottom - top
    
    x = (WIDTH - text_w) // 2
    y = (HEIGHT - text_h) // 2
    
    # Draw text with shadow/outline for better visibility
    outline_color = 'black'
    for adj in range(-2, 3):
        for adj2 in range(-2, 3):
            draw.text((x+adj, y+adj2), processed_text, font=font, fill=outline_color)
            
    draw.text((x, y), processed_text, font=font, fill=color)
    
    # Convert back to numpy array for MoviePy
    img_np = np.array(img_pil)
    
    txt_clip = ImageClip(img_np, duration=duration)
    if bg_color:
        # If a background color is needed (for pure text slides), compose over color
        bg = ColorClip(size=(WIDTH, HEIGHT), color=bg_color, duration=duration)
        return CompositeVideoClip([bg, txt_clip])
    return txt_clip

def create_image_clip(image_path, text, duration, zoom_effect=True):
    """Create a video clip from an image with optional text overlay"""
    if not os.path.exists(image_path):
        print(f"Warning: Image not found {image_path}, using black placeholder")
        return ColorClip(size=(WIDTH, HEIGHT), color=(0,0,0), duration=duration)

    # Load and resize image to fill screen
    clip = ImageClip(image_path)
    
    # Resize to cover
    # ratio = max(WIDTH / clip.w, HEIGHT / clip.h) # v1 way
    # In v2, we might need to be careful with attributes. Assuming .w and .h exist.
    
    # Calculate target size to cover 1280x720
    # We can use resized(height=720) then crop, or calculate manually.
    scale = max(WIDTH / clip.w, HEIGHT / clip.h)
    new_w = int(clip.w * scale)
    new_h = int(clip.h * scale)
    clip = clip.resized(new_size=(new_w, new_h))
    
    # Center crop
    # cropped(x1=None, y1=None, x2=None, y2=None, width=None, height=None, x_center=None, y_center=None)
    clip = clip.cropped(width=WIDTH, height=HEIGHT, x_center=clip.w/2, y_center=clip.h/2)
    clip = clip.with_duration(duration)
    
    # Add simple zoom effect (Ken Burns)
    # if zoom_effect:
    #    clip = clip.resized(lambda t: 1 + 0.04 * t)  # Commented out to avoid v2 complexity for now

    # Add Text Overlay
    txt_clip = create_text_clip(text, duration, font_size=80, color='#FFD700') # Gold color
    
    return CompositeVideoClip([clip, txt_clip])

def main():
    print("Generating Promo Video V3...")
    
    # Asset Paths
    vehicles_dir = "static/images/vehicles"
    items_dir = "static/images/items"
    hostesses_dir = "static/images/hostesses"
    
    # Select specific assets (fallback to available ones)
    def get_asset(directory, preferred_list):
        for name in preferred_list:
            path = os.path.join(directory, name)
            if os.path.exists(path):
                return path
        # Fallback to random jpg
        files = [f for f in os.listdir(directory) if f.endswith('.jpg')]
        if files:
            return os.path.join(directory, files[0])
        return None

    img_car = get_asset(vehicles_dir, ['golf_2.jpg', 'subaru_impreza.jpg'])
    img_gun = get_asset(items_dir, ['ak47.jpg', 'm16.jpg', 'glock.jpg'])
    img_hostess = get_asset(hostesses_dir, ['jasmin.jpg', 'layla.jpg'])
    img_market = get_asset(items_dir, ['gold.jpg', 'energy_drink.jpg', 'tactical_vest.jpg'])

    # Scene Definition
    clips = []
    
    # 1. Intro (Black Screen)
    clips.append(create_text_clip("هل تحلم بالسلطة؟", 2, bg_color=(0,0,0)))
    
    # 2. Rise (Car)
    if img_car:
        clips.append(create_image_clip(img_car, "ابدأ رحلتك", 2.5))
        
    # 3. Action (Gun)
    if img_gun:
        clips.append(create_image_clip(img_gun, "تسلح وواجه", 2.0))
        
    # 4. Hostess (Empire)
    if img_hostess:
        clips.append(create_image_clip(img_hostess, "شكل عصابتك", 2.5))
        
    # 5. Market (Wealth)
    if img_market:
        clips.append(create_image_clip(img_market, "سيطر على السوق", 2.0))
        
    # 6. Ranks (Text Only)
    clips.append(create_text_clip("من لص... إلى العراب", 3, bg_color=(20, 0, 0), font_size=90))
    
    # 7. Outro
    clips.append(create_text_clip("عصابات فلسطين\nانضم الآن", 3, bg_color=(0, 0, 0), font_size=100, color='#FF0000'))

    # Concatenate
    final_video = concatenate_videoclips(clips, method="compose")
    
    # Write file
    final_video.write_videofile(OUTPUT_PATH, fps=24, codec='libx264')
    print(f"Video saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
