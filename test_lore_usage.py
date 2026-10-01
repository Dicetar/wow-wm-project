
import json
import os

lore_file = r'D:/WOW/wm-project/src/wm/lore/lore_indexes.json'

def get_lore_value(category, code):
    if not os.path.exists(lore_file):
        return "Lore file not found."
    with open(lore_file, 'r') as f:
        data = json.load(f)
    return data.get(category, {}).get(str(code), "Unknown")

if __name__ == "__main__":
    print(f"Looking up Faction 68: {get_lore_value('faction_map', 68)}")
    print(f"Looking up Race 5: {get_lore_value('race_map', 5)}")
    print(f"Looking up Class 1: {get_lore_value('class_map', 1)}")
    print(f"Unknown test: {get_lore_value('faction_map', 999)}")
