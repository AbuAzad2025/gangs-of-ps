import os


def create_svg(path, text, color="#3498db"):
    svg_content = f'''<svg width="400" height="300" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="{color}"/>
  <text x="50%" y="50%" font-family="Arial" font-size="24" fill="white" dominant-baseline="middle" text-anchor="middle">{text}</text>
</svg>'''

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"Created: {path}")


base_dir = "d:/gang of Ps/GangsOfPalestine/static/images"

assets = [
    # Items
    {"path": "items/knife.svg", "text": "Kitchen Knife", "color": "#e74c3c"},
    {"path": "items/baton.svg", "text": "Baton", "color": "#7f8c8d"},
    {"path": "items/chain.svg", "text": "Chain", "color": "#95a5a6"},
    {"path": "items/razor.svg", "text": "Razor", "color": "#bdc3c7"},
    {"path": "items/helwan.svg", "text": "Helwan Pistol", "color": "#34495e"},
    {"path": "items/glock.svg", "text": "Glock", "color": "#2c3e50"},
    {"path": "items/ak47.svg", "text": "AK-47", "color": "#c0392b"},
    {"path": "items/m16.svg", "text": "M16", "color": "#27ae60"},
    {"path": "items/light_vest.svg", "text": "Light Vest", "color": "#f1c40f"},
    {"path": "items/leather_jacket.svg",
     "text": "Leather Jacket",
     "color": "#8e44ad"},
    {"path": "items/tactical_vest.svg", "text": "Tactical Vest", "color": "#2c3e50"},
    {"path": "items/medkit.svg", "text": "Medkit", "color": "#e74c3c"},
    {"path": "items/energy_drink.svg", "text": "Energy Drink", "color": "#f39c12"},

    # Crimes / Shared
    {"path": "crimes/wallet.svg", "text": "Wallet Theft", "color": "#f39c12"},
    {"path": "crimes/kiosk.svg", "text": "Kiosk Robbery", "color": "#d35400"},
    {"path": "crimes/phone.svg", "text": "Phone Theft", "color": "#3498db"},
    {"path": "crimes/bike.svg", "text": "Bike Theft", "color": "#1abc9c"},
    {"path": "crimes/atm.svg", "text": "ATM/Pharmacy", "color": "#27ae60"},
    {"path": "crimes/wall.svg", "text": "Wall Smuggling", "color": "#7f8c8d"},
    {"path": "crimes/extortion.svg", "text": "Extortion", "color": "#c0392b"},
    {"path": "crimes/arms_deal.svg", "text": "Arms Deal", "color": "#2c3e50"},
    {"path": "crimes/jewelry.svg", "text": "Jewelry Heist", "color": "#9b59b6"},
    {"path": "crimes/car_theft.svg", "text": "Car Theft", "color": "#e67e22"},
    {"path": "crimes/smuggling.svg", "text": "Smuggling", "color": "#16a085"},
    {"path": "crimes/cyber.svg", "text": "Cyber Crime", "color": "#2980b9"},
    {"path": "crimes/bank_heist.svg", "text": "Bank Heist", "color": "#2c3e50"},
    {"path": "crimes/boss.svg", "text": "Boss Mission", "color": "#8e44ad"},

    # Vehicles
    {"path": "vehicles/subaru_impreza.svg",
        "text": "Subaru Impreza", "color": "#3498db"},
    {"path": "vehicles/golf_2.svg", "text": "Golf 2", "color": "#f1c40f"},
    {"path": "vehicles/skoda_octavia.svg",
        "text": "Skoda Octavia", "color": "#bdc3c7"},
    {"path": "vehicles/mazda_3.svg", "text": "Mazda 3", "color": "#95a5a6"},
    {"path": "vehicles/hyundai_accent.svg",
        "text": "Hyundai Accent", "color": "#ecf0f1"},

    # Locations
    {"path": "locations/jerusalem.svg", "text": "Jerusalem", "color": "#f39c12"},
    {"path": "locations/gaza.svg", "text": "Gaza", "color": "#3498db"},
    {"path": "locations/nablus.svg", "text": "Nablus", "color": "#2ecc71"},
    {"path": "locations/hebron.svg", "text": "Hebron", "color": "#e74c3c"},
    {"path": "locations/ramallah.svg", "text": "Ramallah", "color": "#9b59b6"},
    {"path": "locations/jenin.svg", "text": "Jenin", "color": "#16a085"},
    {"path": "locations/jericho.svg", "text": "Jericho", "color": "#f1c40f"},
    {"path": "locations/bethlehem.svg", "text": "Bethlehem", "color": "#e67e22"},
    {"path": "locations/tulkarm.svg", "text": "Tulkarm", "color": "#95a5a6"},

    # Hostesses
    {"path": "hostesses/layla.svg", "text": "Layla", "color": "#8e44ad"},
    {"path": "hostesses/sarah.svg", "text": "Sarah", "color": "#2ecc71"},
    {"path": "hostesses/ruby.svg", "text": "Ruby", "color": "#c0392b"},
    {"path": "hostesses/jasmin.svg", "text": "Jasmin", "color": "#f1c40f"},

    # Extra Items / Materials
    {"path": "items/explosives.svg", "text": "Explosives", "color": "#2c3e50"},
    {"path": "items/keffiyeh.svg", "text": "Keffiyeh", "color": "#ecf0f1"},
]

for asset in assets:
    full_path = os.path.join(base_dir, asset["path"])
    create_svg(full_path, asset["text"], asset["color"])
