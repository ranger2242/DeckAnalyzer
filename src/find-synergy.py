
import os
import sys
import csv
import json
import re
import time
import requests
from glob import glob
from collections import defaultdict
from pandas import DataFrame
from tqdm import tqdm
from colorama import init, Fore, Style
init(autoreset=True)



import sys
import os
from datetime import datetime

# Setup logging
log_folder = "./logs"
os.makedirs(log_folder, exist_ok=True)
log_path = os.path.join(log_folder, f"log_20250416_032315.txt")
sys.stdout = open(log_path, "w")
sys.stderr = sys.stdout
print(f"🔧 Logging to: {log_path}\n")

import sys
import os
from datetime import datetime

class DualLogger:
    def __init__(self, filepath, mode="w", encoding="utf-8"):
        self.terminal = sys.__stdout__
        self.log = open(filepath, mode, encoding=encoding, buffering=1)
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
    def flush(self):
        self.terminal.flush()
        self.log.flush()

# Setup logging with both console + file output
log_folder = "./logs"
os.makedirs(log_folder, exist_ok=True)
log_path = os.path.join(log_folder, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
sys.stdout = sys.stderr = DualLogger(log_path)
print(f"🔧 Logging to: {log_path}\n")
# ========== 1-get-edhrec-card-data.py ==========
def format_card_name(name):
    name = name.lower()
    name = re.sub(r"[^\w\s-]", "", name)
    return name.replace(" ", "-")

def fetch_synergy_data(card_name):
    formatted_name = format_card_name(card_name)
    folder = "./edhrec-card-data"
    os.makedirs(folder, exist_ok=True)
    filename = f"{folder}/{formatted_name}_synergy.csv"
    
    if os.path.exists(filename):
        file_time = datetime.fromtimestamp(os.path.getmtime(filename))
        if datetime.now() - file_time < timedelta(weeks=1):
            print(f"⏩ Using cached EDHREC data for '{card_name}'")
            return None, formatted_name

    url = f"https://json.edhrec.com/pages/cards/{formatted_name}.json"
    synergy_data = []

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        cardlists = data.get("container", {}).get("json_dict", {}).get("cardlists", [])

        for section in cardlists:
            for card in section.get("cardviews", []):
                name = card.get("name")
                label = card.get("label", "")
                match = re.search(r"([+-]?\d+)%", label)
                if name and match:
                    synergy = int(match.group(1))
                    synergy_data.append((name, synergy))

    except requests.exceptions.RequestException:
        print(f"⚠️  Failed to fetch data for '{card_name}'")

    return synergy_data, formatted_name

def write_synergy_csv(card_name, synergy_data, formatted_name):
    unique_cards = {}
    for name, synergy in synergy_data:
        if name not in unique_cards or synergy > unique_cards[name]:
            unique_cards[name] = synergy

    sorted_cards = sorted(unique_cards.items(), key=lambda x: x[1], reverse=True)
    folder = "./edhrec-card-data"
    if not os.path.exists(folder):
        os.makedirs(folder)
    filename = f"{folder}/{formatted_name}_synergy.csv"
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["card name", "synergy %"])
        for name, synergy in sorted_cards:
            writer.writerow([name, synergy])

    print(Fore.GREEN + f"✅ Saved: {filename}")

def edhrec_main(input_file):
    with open(input_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in tqdm(lines, desc='📥 Fetching EDHREC Data', colour='cyan'):
            card_name = line.strip()
            if card_name:
                data, formatted = fetch_synergy_data(card_name)
                if data:
                    write_synergy_csv(card_name, data, formatted)

# ========== 2-combine-synergy-list.py ==========
def read_top_synergy(file_path, max_rows=50):
    entries = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            if len(row) >= 2:
                name, synergy = row[0], row[1]
                try:
                    synergy_val = int(synergy)
                    entries.append((name, synergy_val))
                except ValueError:
                    continue
    return entries

def combine_csvs(folder_path):
    all_entries = []

    csv_files = glob(os.path.join(folder_path, "*.csv"))
    if not csv_files:
        print("❌ No CSV files found in that folder.")
        return

    for file in tqdm(csv_files, desc='🔀 Combining CSVs', colour='magenta'):
        entries = read_top_synergy(file)
        all_entries.extend(entries)

    unique_entries = {}
    for name, synergy in all_entries:
        if name not in unique_entries or synergy > unique_entries[name]:
            unique_entries[name] = synergy

    sorted_entries = sorted(unique_entries.items(), key=lambda x: x[1], reverse=True)
    folder = "./edhrec-card-data/combined"
    if not os.path.exists(folder):
        os.makedirs(folder)

    output_file = f"{folder}/combined_top50_synergy.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["card name", "synergy %"])
        for name, synergy in sorted_entries:
            writer.writerow([name, synergy])
    return output_file

# ========== 3-get-scryfall-card-data.py ==========
def safe_card_filename(card_name):
    return card_name.lower().replace(" ", "_").replace("/", "-")

def load_or_fetch_card(card_name, cache_dir="./scryfall-data"):
    os.makedirs(cache_dir, exist_ok=True)
    safe_name = safe_card_filename(card_name)
    filepath = os.path.join(cache_dir, f"{safe_name}.json")

    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ Skipping corrupt file: {filepath}")
                return None

    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        time.sleep(0.1)
        return data
    except:
        print(f"❌ Failed to fetch: {card_name}")
        return None

def get_power_tough(da, key):
    try:
        return int(da[key]) if key in da and da[key].isdigit() else 0
    except:
        return 0

def enrich_with_scryfall(input_file):
    synergy_map = defaultdict(list)
    with open(input_file, "r", encoding="utf-8") as csvfile:
    # Force synergy to 100% if card is on the input list
        card_names_from_input = set(synergy_map.keys())

        reader = csv.DictReader(csvfile)
        for row in reader:
            card_name = row.get("card name")
            synergy = row.get("synergy %")
            if card_name and synergy:
                try:
                    synergy_map[card_name].append(int(synergy))
                except ValueError:
                    continue

    
    for name in card_names_from_input:
        synergy_map[name] = [100]

    avg_synergy = {
        name: sum(values) / len(values)
        for name, values in synergy_map.items()
    }

    entries = {}
    for card_name in tqdm(avg_synergy, desc='✨ Enriching with Scryfall', colour='green'):
        data = load_or_fetch_card(card_name)
        if not data or "card_faces" in data:
            continue

        name = data["name"]
        type_line = data["type_line"]
        cmc = data.get("cmc", 0)
        colors = data.get("colors", [])
        produced = data.get("produced_mana", [])
        power = get_power_tough(data, "power")
        toughness = get_power_tough(data, "toughness")
        keywords = data.get("keywords", [])
        text = data.get("oracle_text", "")
        legal = int(data.get("legalities", {}).get("commander", "") == "legal")
        rank = data.get("edhrec_rank", 10000)
        img = data.get("image_uris", {}).get("png", "")
        art = data.get("image_uris", {}).get("art_crop", "")
        url = data.get("purchase_uris", {}).get("tcgplayer", "")
        prices = data.get("prices", {})
        usd = prices.get("usd", "")
        usd_foil = prices.get("usd_foil", "")
        eur = prices.get("eur", "")
        avg = round(avg_synergy[card_name], 2)

        entries[name] = [
            name, type_line, cmc, colors, produced, power, toughness,
            keywords, text, legal, rank, img, art, url, usd, usd_foil, eur, avg
        ]

    df = DataFrame(
        list(entries.values()),
        columns=[
            "name", "type", "mana_cost", "colors", "produced_mana",
            "power", "tough", "keywords", "text", "legal", "rank",
            "png", "art", "url", "usd", "usd_foil", "eur", "avg_synergy"
        ]
    )
    df.to_csv("./output/synergy-data.csv", index=False)
    print(Fore.GREEN + "✅ Output saved to: scryfall_output.csv")

# ========== COMBINED EXECUTION ==========
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python full_pipeline.py <commander_list.txt>")
        sys.exit(1)

    edhrec_main(sys.argv[1])
    combined_csv = combine_csvs("./edhrec-card-data")
    if combined_csv:
        enrich_with_scryfall(combined_csv)
