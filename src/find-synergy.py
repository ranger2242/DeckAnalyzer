
import os
import sys
import json
import csv
import re
import time
import requests
import pandas as pd
from collections import defaultdict
from tqdm import tqdm
import logging
import math

def safe_card_filename(card_name):
    return card_name.lower().replace(" ", "_").replace("/", "-")

def format_card_name(name):
    name = name.lower()
    name = re.sub(r"[^\w\s-]", "", name)
    return name.replace(" ", "-")

def fetch_scryfall(card_name, cache_dir="./scryfall-data"):
    os.makedirs(cache_dir, exist_ok=True)
    safe_name = safe_card_filename(card_name)
    filepath = os.path.join(cache_dir, f"{safe_name}.json")
    if os.path.exists(filepath):
        return
    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(response.json(), f, indent=2)
        time.sleep(0.1)
    except:
        print(f"❌ Failed to fetch from Scryfall for {card_name}")

def fetch_edhrec(card_name, folder="./edhrec-card-data"):
    os.makedirs(folder, exist_ok=True)
    formatted = format_card_name(card_name)
    path = os.path.join(folder, f"{formatted}_synergy.csv")
    if os.path.exists(path):
        return
    url = f"https://json.edhrec.com/pages/cards/{formatted}.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        cardlists = data.get("container", {}).get("json_dict", {}).get("cardlists", [])
        synergy_cards = []
        for section in cardlists:
            for card in section.get("cardviews", []):
                name = card.get("name")
                label = card.get("label", "")
                match = re.search(r"([+-]?\d+)%", label)
                if name and match:
                    synergy = int(match.group(1))
                    synergy_cards.append((name, synergy))
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["card name", "synergy %"])
            for name, synergy in synergy_cards:
                writer.writerow([name, synergy])
    except:
        print(f"⚠️ Could not fetch EDHREC for {card_name}")


def fetch_commander_data(card_name, folder="./edhrec-commander-data"):
    os.makedirs(folder, exist_ok=True)
    formatted = format_card_name(card_name)
    path = os.path.join(folder, f"{formatted}_commander.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return None
    url = f"https://json.edhrec.com/pages/commanders/{formatted}.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data
    except:
        print(f"⚠️ Could not fetch EDHREC commander data for {card_name}")
        return None


def read_synergy_csv(formatted_name, folder="./edhrec-card-data"):
    synergy_pairs = []
    filepath = os.path.join(folder, f"{formatted_name}_synergy.csv")
    if not os.path.exists(filepath):
        return synergy_pairs
    with open(filepath, "r", encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 2:
                try:
                    synergy = int(parts[1])
                    if synergy > 0:
                        synergy_pairs.append((parts[0], synergy))
                except ValueError:
                    continue
    return synergy_pairs

def load_scryfall_data(card_name, cache_dir="./scryfall-data"):
    safe_name = safe_card_filename(card_name)
    filepath = os.path.join(cache_dir, f"{safe_name}.json")

    # Try loading cached file
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"⚠️ Corrupt cache, re-fetching: {card_name}")
    
    # Fetch and retry if not found or corrupt
    fetch_scryfall(card_name)
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"❌ Still corrupt after re-fetch: {card_name}")
    return None

def extract_value(data, key, default=""):
    try:
        return data.get(key, default)
    except:
        return default

def get_power_tough(data, key):
    val = data.get(key, "")
    return val if isinstance(val, str) else str(val)


def get_deck_color_identity(card_names):
    identity_set = set()
    for card in tqdm(card_names, desc="🔎 Fetching Scryfall + EDHREC data"):
        data = load_scryfall_data(card)
        if data:
            identity_set.update(data.get("color_identity", []))
    return identity_set

def generate_enriched_synergy_data(card_list_path):
    synergy_accumulator = defaultdict(list)
    card_names = []

    with open(card_list_path, "r", encoding="utf-8") as file:
        
    
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
        logging.info("📥 Loading deck and initializing filters...")

        card_names = [line.strip() for line in file if line.strip()]
        normalized_input = set(map(str.lower, map(str.strip, card_names)))
        deck_colors = get_deck_color_identity(card_names)
        # Gather all keywords from input cards
        input_keywords = set()
        for card in card_names:
            scry = load_scryfall_data(card)
            if scry:
                input_keywords.update(scry.get("keywords", []))

        for card in card_names:
            fetch_scryfall(card)
            fetch_edhrec(card)

        ln = len(card_names)
        for ind, card in enumerate(card_names):
            percent = int((ind / ln) * 100)
            print(card, " ", percent, "%")
            formatted = format_card_name(card)

            # Regular EDHREC synergy data
            synergy_cards = read_synergy_csv(formatted)
            for partner, score in synergy_cards:
                synergy_accumulator[partner].append(score)

            # If commander, add commander synergy
            scry_data = load_scryfall_data(card)
            if scry_data and "Legendary Creature" in scry_data.get("type_line", ""):
                commander_data = fetch_commander_data(card)
                if commander_data:
                    cardlists = commander_data.get("container", {}).get("json_dict", {}).get("cardlists", [])
                    for section in cardlists:
                        for cmd_card in section.get("cardviews", []):
                            name = cmd_card.get("name")
                            label = cmd_card.get("label", "")
                            match = re.search(r"([+-]?\d+)%", label)
                            if name and match:
                                synergy = int(match.group(1))
                                synergy_accumulator[name].append(synergy)


               # synergy_accumulator[partner].append(score)

    weighted_scores = {
        card: round(sum(scores) + len(scores) * 3, 2)
        for card, scores in synergy_accumulator.items()
        if card not in card_names
    }

    
    filtered_sorted = []
    for card, synergy_score in weighted_scores.items():
        if card.lower().strip() in normalized_input:
            continue
        scry = load_scryfall_data(card)
        if not scry:
            print(f"❌ Missing Scryfall: {card}")
            continue
        if scry.get("color_identity") and not set(scry["color_identity"]).issubset(deck_colors):
           # print(f"⚠️ Color identity mismatch: {card} => {scry.get('color_identity')} not in {deck_colors}")
            continue
        print(card," ", )

        # Keyword weighting
        card_keywords = set(scry.get("keywords", []))
        keyword_overlap = len(input_keywords & card_keywords)
        keyword_boost = keyword_overlap * 2
        synergy_score += keyword_boost

        # CMC inverse weighting
        type_line = scry.get("type_line", "")
        if "Land" not in type_line:
            cmc = scry.get("cmc", 0)
            try:
                cmc = float(cmc)
                if cmc > 0:
                    cmc_weight = 5 / cmc  # Adjust constant as needed
                    synergy_score += cmc_weight
            except:
                pass

        filtered_sorted.append((card, synergy_score))



    rows = []
    if filtered_sorted:
        max_score = max(score for _, score in filtered_sorted)
        temp_rows = []
        for card, synergy_score in filtered_sorted:
            normalized_score = math.ceil((synergy_score / max_score) * 10000)
            scry = load_scryfall_data(card)
            if not scry or "card_faces" in scry:
                continue
            if scry.get("color_identity") and not set(scry["color_identity"]).issubset(deck_colors):
                continue

            prices = scry.get("prices", {})
            row = {
                "usd": prices.get("usd", ""),
                "name": scry["name"],
                "synergy": normalized_score,
                "type": extract_value(scry, "type_line"),
                "mana_cost": extract_value(scry, "mana_cost"),
                "colors": ",".join(scry.get("colors", [])),
                "produced_mana": ",".join(scry.get("produced_mana", [])),
                "power": get_power_tough(scry, "power"),
                "tough": get_power_tough(scry, "toughness"),
                "keywords": ",".join(scry.get("keywords", [])),
                "rarity": extract_value(scry, "rarity"),
                "text": extract_value(scry, "oracle_text"),
                "rank": scry.get("edhrec_rank", ""),
                "png": extract_value(scry.get("image_uris", {}), "png"),
                "art": extract_value(scry.get("image_uris", {}), "art_crop"),
                "url": extract_value(scry.get("purchase_uris", {}), "tcgplayer")
            }
            temp_rows.append(row)

# Sort by synergy before writing to CSV
    rows = sorted(temp_rows, key=lambda x: x["synergy"], reverse=True)



    logging.info("📊 Writing synergy results to CSV...")
    df = pd.DataFrame(rows)
    os.makedirs("./output", exist_ok=True)
    csv_path = "./output/top_synergy_cards.csv"
    try:
        df.to_csv(csv_path, index=False)
    except PermissionError:
        fallback_path = "./output/top_synergy_cards_1.csv"
        print("⚠️ File in use, saving to:", fallback_path)
        df.to_csv(fallback_path, index=False)
    print(f"✅ Saved top synergy data to {csv_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python deck_synergy_builder.py <deck_list.txt>")
        sys.exit(1)
    generate_enriched_synergy_data(sys.argv[1])
