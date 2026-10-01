
import csv
import os

# The path to our lore directory
LORE_DIR = r'D:/WOW/wm-project/src/wm/lore/'

def get_lore_value(category_name, code):
    file_path = os.path.join(LORE_DIR, f"{category_name}_map.csv")
    if not os.path.exists(file_path):
        return "Lore file not found."

    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['code'] == str(code):
                return row['name']
    return "Unknown code"

if __name__ == "__main__":
    print(f"--- Lore CSV TEST ---")
    print(f"Lookup Faction 68: {get_lore_value('faction', 68)}")
    print(f"Lookup Race 5: {get_lore_value('race', 5)}")
    print(f"Lookup Class 1: {get_lore_value('class', 1)}")
    print(f"Unknown test: {get_lore_value('faction', 999)}")
