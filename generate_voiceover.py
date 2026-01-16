from gtts import gTTS
import os

texts = [
    ("intro1", "Azad Company Presents"),
    ("intro2", "A Masterpiece by Master User Azad"),
    ("intro3", "Gangs of Palestine. The Ultimate Strategy RPG"),
    ("slide1", "Explore the Streets"),
    ("slide2", "Train for Power"),
    ("slide3", "Dominate the Economy"),
    ("slide4", "Manage Your Wealth"),
    ("slide5", "Ride in Style"),
    ("slide6", "High Stakes Gambling"),
    ("slide7", "Luxury Lifestyle"),
    ("slide8", "Brutal Combat"),
    ("slide9", "Gather Intel"),
    ("slide10", "Total Control"),
    ("trans1", "Full Arabic Localization"),
    ("trans2", "A Complete Arabic Experience"),
    ("outro1", "Join the Gang"),
    ("outro2", "Play Now at localhost 8000"),
    ("outro3", "Azad Company"),
]

os.makedirs("static/audio", exist_ok=True)

for name, text in texts:
    print(f"Generating {name}...")
    # British accent is often more 'cinematic' or just different
    tts = gTTS(text=text, lang='en', tld='co.uk')
    tts.save(f"static/audio/{name}.mp3")

print("All audio files generated.")
