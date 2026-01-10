import os
import requests
import re
import time
import random

# Base directory for images
BASE_DIR = os.path.join(os.getcwd(), 'static', 'images')
HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ),
    'Accept': (
        'text/html,application/xhtml+xml,application/xml;q=0.9,'
        'image/avif,image/webp,image/apng,*/*;q=0.8,'
        'application/signed-exchange;v=b3;q=0.9'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

# Mapping: Local Path (relative to static/images) -> Wikimedia Filename
IMAGES_TO_DOWNLOAD = {
    # Locations
    'locations/jerusalem.jpg': 'Jerusalem_Dome_of_the_rock_BW_14.JPG',
    'locations/gaza.jpg': 'Gaza_Beach.jpg',
    'locations/nablus.jpg': 'Al_Hanbali_Mosque_Nablus_Interior.jpg',
    'locations/hebron.jpg': 'Ibrahimi_mosque_-Hebron.jpg',
    'locations/ramallah.jpg': 'Al-Manara_Square,_Ramallah.jpg',
    'locations/jenin.jpg': 'Jenin_city_banner.JPG',
    'locations/jericho.jpg': "Hisham's_Palace_P1190942.JPG",
    'locations/bethlehem.jpg': 'Church_of_the_Nativity.jpg',
    'locations/tulkarm.jpg': 'Mosque_in_Tulkarm.JPG',

    # Basic Crimes
    'crimes/wallet.jpg': 'Pickpocket.jpg',
    'crimes/kiosk.jpg': 'Grocery_store.jpg',
    'crimes/phone.jpg': 'Hand_held_phones.JPG',
    'crimes/bike.jpg': 'Bicycle_parking_lot.jpg',
    'crimes/pharmacy.jpg': 'Highland_Park_Pharmacy_interior_01.jpg',
    'crimes/wall.jpg': 'Israeli_West_Bank_barrier.jpg',
    'crimes/extortion.jpg': 'Broken_window.jpg',
    'crimes/arms_deal.jpg': 'AK-47_assault_rifle.jpg',
    'crimes/jewelry.jpg': 'Gold_jewelry.jpg',
    'crimes/car_theft.jpg': 'Broken_car_window.jpg',
    'crimes/atm.jpg': 'ATM.jpg',
    'crimes/smuggling.jpg': (
        'Intermodal_shipping_containers_on_a_railway_flat_car.jpg'),
    'crimes/cyber.jpg': 'Binary_1-7.PNG',
    'crimes/bank_heist.jpg': 'Bank_of_Quitman_Interior_03.jpg',
    'crimes/armored_van.jpg': (
        'CTK_armored_van_on_the_Philippine_island_of_Palawan.jpg'),
    'crimes/casino.jpg': 'Roulette_wheel.jpg',

    # Items (Weapons & Armor)
    'items/knife.jpg': 'Kitchen_knife.jpg',
    'items/baton.jpg': 'Police_baton.jpg',
    'items/chain.jpg': 'Rusty_chain.jpg',
    'items/razor.jpg': 'Razor_blade.jpg',
    'items/helwan.jpg': 'Helwan_9mm_pistol.jpg',
    'items/glock.jpg': 'Glock_17_Gen_4.jpg',
    'items/ak47.jpg': 'AK-47_assault_rifle.jpg',
    # Using standard for now, gold is rare on commons
    'items/golden_ak47.jpg': 'AK-47_assault_rifle.jpg',
    'items/m16.jpg': 'M16A1_rifle.jpg',
    'items/light_vest.jpg': (
        'Giubetto_Antiproiettile_-_standard_issue_balllstic_vest.png'),
    'items/leather_jacket.jpg': 'Leather_jacket.jpg',
    'items/tactical_vest.jpg': 'Interceptor_Body_Armor.jpg',
    'items/keffiyeh.jpg': 'Palestinian_keffiyeh.jpg',
    'items/explosives.jpg': (
        '160mm_Mortar_bomb_HE_TNT,_photographed_at_the_'
        'Aalborg_Forsvars-_og_Garnisonsmuseum.JPG'),
    'items/molotov.jpg': (
        'Detail_of_Molotov_Cocktail_-_Museum_of_the_Great_Patriotic_War_-_'
        'Minsk_-_Belarus_(26916185674).jpg'),

    # Items (Consumables & Misc)
    'items/medkit.jpg': 'First_aid_kit_showing_lid_with_crest_and_caption.jpg',
    'items/energy_drink.jpg': 'Red_Bull_energy_drink.jpg',
    'items/smoke_grenade.jpg': 'SmokeGrenade2.JPG',
    'items/jammer.jpg': 'Cell_phone_jammer.jpg',

    # Vehicles
    'vehicles/subaru_impreza.jpg': 'Subaru_Impreza_2.0_GL_AWD.JPG',
    'vehicles/golf_2.jpg': '1988_Volkswagen_Golf_1.3_rear.jpg',
    'vehicles/skoda_octavia.jpg': 'Skoda_Octavia.JPG',
    'vehicles/mazda_3.jpg': 'Mazda_3_Facelift_front.JPG',
    'vehicles/hyundai_accent.jpg': 'Hyundai_Accent_2005.JPG',
    'vehicles/mercedes_g_class.jpg': (
        'Mercedes_G-Klasse_Edition_Pur_20090808_front.JPG'),
}


def get_image_url(filename):
    url = f"https://commons.wikimedia.org/wiki/File:{filename}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            print(f"[-] Failed to fetch page for {filename}: {r.status_code}")
            return None

        # Try 1: Original upload
        match = re.search(
            r'href="(https://upload\.wikimedia\.org/wikipedia/commons/[^"]+)" '
            r'class="internal"', r.text)
        if match:
            return match.group(1)

        # Try 2: Full Media div
        match = re.search(
            r'<div class="fullMedia"><a href="'
            r'(https://upload\.wikimedia\.org/wikipedia/commons/[^"]+)"',
            r.text)
        if match:
            return match.group(1)

        # Try 3: contentUrl property
        match = re.search(
            r'"contentUrl":\s*"(https://upload\.wikimedia\.org/wikipedia/'
            r'commons/[^"]+)"', r.text)
        if match:
            return match.group(1)

        print(f"[-] Could not find image URL in page for {filename}")
        return None
    except Exception as e:
        print(f"[-] Exception fetching {filename}: {e}")
        return None


def download_file(url, local_path):
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        r = requests.get(url, headers=HEADERS, stream=True, timeout=20)
        if r.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            print(f"[+] Downloaded to {local_path}")
            return True
        else:
            print(
                f"[-] Failed to download content from {url}: {r.status_code}")
            return False
    except Exception as e:
        print(f"[-] Exception downloading to {local_path}: {e}")
        return False


def main():
    print("Starting image download...")

    # Ensure directories exist
    for subdir in ['locations', 'crimes', 'items', 'vehicles']:
        os.makedirs(os.path.join(BASE_DIR, subdir), exist_ok=True)

    for local_rel, wiki_name in IMAGES_TO_DOWNLOAD.items():
        local_full = os.path.join(BASE_DIR, local_rel)

        # Check if file exists and is not empty
        if os.path.exists(local_full) and os.path.getsize(local_full) > 0:
            print(f"[.] Skipping {local_rel} (already exists)")
            continue

        print(f"[*] Processing {local_rel} -> {wiki_name}")
        image_url = get_image_url(wiki_name)

        if image_url:
            if download_file(image_url, local_full):
                # Random delay to be nice and avoid 429
                sleep_time = random.uniform(5.0, 10.0)
                print(f"[*] Sleeping for {sleep_time:.2f}s...")
                time.sleep(sleep_time)
            else:
                print(f"[-] Failed to download {local_rel}")
        else:
            print(f"[-] Failed to get URL for {local_rel}")
            # Try to create a dummy placeholder if it fails?
            # No, better to leave it missing so we know.

    print("Download complete.")


if __name__ == "__main__":
    main()
