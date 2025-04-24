
from importlib.metadata import distribution
import os
import sys
import json
import requests
from collections import defaultdict
from tqdm import tqdm
from colorama import Fore, init, Style
import random
from collections import Counter
from datetime import datetime
import re

init(autoreset=True)

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
        return data
    except:
        print(f"❌ Failed to fetch: {card_name}")
        return None

loaded_card_data ={}

def format_mana_cost(mana_cost, color_map):
    formatted = ""
    pattern = re.compile(r'\{(.*?)\}')
    symbols = pattern.findall(mana_cost.upper())
    for sym in symbols:
        for c in ["W", "U", "B", "R", "G", "C"]:
            if c in sym:
                formatted += f"{Fore.RESET}({color_map[c]})"
                break
        else:
            formatted += f"({sym})"
    return formatted

def simulate_opening_hands(card_names, iterations=10000):
    global loaded_card_data
    print("\n[SIMULATING] Fetching card types, CMCs, and colors...")
    land_cards = set()
    cmc_lookup = {}
    color_lookup = {}
    produces_lookup = {}

    deck = []

    for name in tqdm(card_names, desc="Classifying Cards", colour="green"):
        data = load_or_fetch_card(name)
        loaded_card_data[name] = data;
        if not data:
            continue
        type_line = data.get("type_line", "").lower()
        cmc = int(data.get("cmc", 0))
        colors = data.get("colors", [])
        produced = data.get("produced_mana", []) if "land" in type_line else []

        if "land" in type_line:
            land_cards.add(name)

        cmc_lookup[name] = cmc
        color_lookup[name] = colors
        produces_lookup[name] = produced
        deck.append(name)

    if len(deck) < 7:
        print("Deck is too small for simulation.")
        return

    land_draws = Counter()
    cmc_stats = {"CMC1+": 0, "CMC2+": 0, "CMC3+": 0}

    color_stats = {
        c: {"producer_hits": [], "cmc_vals": []}
        for c in ["W", "U", "B", "R", "G"]
    }

    for _ in range(iterations):
        hand = random.sample(deck, 7)
        land_count = sum(1 for card in hand if card in land_cards)
        land_draws[land_count] += 1

        cmcs = [cmc_lookup.get(card, 0) for card in hand]
        if any(c == 1 for c in cmcs): cmc_stats["CMC1+"] += 1
        if any(c <= 2 and c>=1 for c in cmcs): cmc_stats["CMC2+"] += 1
        if any(c <= 3 and c>=1 for c in cmcs): cmc_stats["CMC3+"] += 1

        # For each color, count producers and CMC values that use that color
        for color in color_stats.keys():
            producer_count = sum(1 for card in hand if color in produces_lookup.get(card, []))
            cmc_values = [cmc_lookup[card] for card in hand if color in color_lookup.get(card, [])]
            color_stats[color]["producer_hits"].append(producer_count / 7 * 100)
            if cmc_values:
                avg = sum(cmc_values) / len(cmc_values)
                color_stats[color]["cmc_vals"].append(avg)

    print("\nCombined Opening Hand Simulation Summary (One Table):")
    print("=" * 132)
    print(f"{'Lands':<5} | {'% Hands':>8} |===| "
          f"{'CMC Tier':<7} | {'# Hands':>8} | {'%':>6} |===| "
          f"{'Color':<5} | {'% Producers':>12} | {'Avg CMC':>9} | {'Avg Count':>10}")
    print("-" * 132)

    land_keys = list(range(8))
    cmc_keys = list(cmc_stats.keys())
    colors = ["W", "U", "B", "R", "G"]
    rows = max(len(land_keys), len(cmc_keys), len(colors))

    for i in range(rows):
        # LAND STATS
        if i < len(land_keys):
            land_str = f"{land_keys[i]}"
            land_pct = f"{(land_draws[land_keys[i]] / iterations * 100):>7.2f}%"
        else:
            land_str = ""
            land_pct = ""

        # CMC STATS
        if i < len(cmc_keys):
            cmc_label = cmc_keys[i]
            val = cmc_stats[cmc_label]
            cmc_val = f"{val:>8}"
            cmc_pct = f"{(val / iterations * 100):>5.2f}%"
        else:
            cmc_label, cmc_val, cmc_pct = "", "", ""

        # COLOR STATS
        if i < len(colors):
            c = colors[i]
            color = c
            pprod = f"{sum(color_stats[c]['producer_hits']) / iterations:>11.2f}%"
            if color_stats[c]["cmc_vals"]:
                avg_cmc = f"{sum(color_stats[c]['cmc_vals']) / len(color_stats[c]['cmc_vals']):>8.2f}"
            else:
                avg_cmc = " " * 8
            color_cost_total = sum(
                sum(1 for card in random.sample(deck, 7) if c in color_lookup.get(card, []))
                for _ in range(iterations)
            )
            avg_count = f"{color_cost_total / iterations:>9.2f}"
        else:
            color, pprod, avg_cmc, avg_count = "", "", "", ""

        print(f"{land_str:<5} | {land_pct:>8} |===| "
              f"{cmc_label:<7} | {cmc_val:>8} | {cmc_pct:>6} |===| "
              f"{color:<5} | {pprod:>12} | {avg_cmc:>9} | {avg_count:>10}")

    print("=" * 132)







def analyze_mana_distribution(card_names, landcount):
    color_count = defaultdict(int)
    producer_cards = defaultdict(list)
    type_cards = defaultdict(list)
    damage_cards = []
    removal_cards = []
    cmc_list = []
    draw_cards = []
    discard_cards = []
    mill_cards = []
    heal_cards = []
    scry_cards = []
    combo_cards = []
    token_cards = []
    search_cards = []
    graveyard_cards = []
    total = 0

    for card_name in tqdm(card_names, desc="Analyzing Cards", colour="cyan"):
        data = load_or_fetch_card(card_name)
        if not data:
            continue
        type_line = data.get("type_line", "").lower()
        text = data.get("oracle_text", "").lower()

        # Color count
        colors = data.get("colors", [])
        for c in colors:
            color_count[c] += 1
            total += 1
        mana_cost = data.get("mana_cost", "").upper()
        if not any(c in mana_cost for c in ["W", "U", "B", "R", "G"]) and "land" not in type_line:
            color_count["C"] += 1
            total += 1

        # Produced mana
        for produced in data.get("produced_mana", []):
            if "treasure" in text:
                continue
            producer_cards[produced].append(data["name"])

        # Type and tag matching
        name = data["name"]
        # Remove text in parentheses
        text = re.sub(r'\([^)]*\)', '', text)
        cmc = data.get("cmc", 0)
        cmc_list.append((name, cmc))

        for t in ["instant", "sorcery", "land", "creature", "artifact", "enchantment", "planeswalker", "battle", "vehicle", "equipment", "aura"]:
            if t in type_line:
                type_cards[t].append(name)

        if any(word in text for word in ["damage", "deals", "burn"]):
            damage_cards.append(name)
        if "creature" in type_line:
            damage_cards.append(name)

        if any(word in text for word in ["destroy", "exile", "sacrifice", "remove"]):
            removal_cards.append(name)
        if any(word in text for word in ["draw a card", "draw cards"]):
            draw_cards.append(name)
        if any(word in text for word in ["discard", "each player discards", "target player discards"]):
            discard_cards.append(name)
        if any(word in text for word in ["mill", "put the top", "put the top card", "library into their graveyard"]):
            mill_cards.append(name)
        if any(word in text for word in ["gain life", "you gain", "lifelink"]):
            heal_cards.append(name)
        if any(word in text for word in ["scry", "surveil", "look at"]):
            scry_cards.append(name)
        if any(word in text for word in ["infinite", "untap", "combo","win", "lose", "whenever you cast"]):
            combo_cards.append(name)
        if any(word in text for word in ["create a token", "create x", "create one", "create two", "put a", "create a"]) and "token" in text:
            token_cards.append(name)
        if any(word in text for word in ["search your library", "search their library", "tutor"]):
            search_cards.append(name)
        if any(word in text for word in ["graveyard"]):
            graveyard_cards.append(name)
  
    if total == 0:
        print(Fore.YELLOW + "No color data found.")
        return

    total_cards = sum(len(cards) for cards in type_cards.values())

    print(Fore.BLUE + "\nCard Type Summary:" + Style.RESET_ALL)
    print("-" * 55)
    print(f"{'Type':<20} | {'# Cards':<10} | {'% of Total'}")
    print("-" * 55)
    for t in sorted(type_cards.keys()):
        count = len(type_cards[t])
        percent = (count / total_cards) * 100 if total_cards else 0
        print(f"{t.title():<20} | {count:<10} | {percent:>10.2f}%")
    print("-" * 55)


    print(Fore.CYAN + "\nMana Color Distribution:")
    percentages = {}

    def bonk(cl,tx):
        return cl + tx+ Style.RESET_ALL
    color_map2 = {
        "W":Fore.WHITE,
        "U": Fore.BLUE ,
        "B": Fore.LIGHTBLACK_EX ,
        "R":Fore.RED,
        "G":Fore.GREEN ,
        "C": Fore. LIGHTWHITE_EX ,
    }   

    color_map = {
        "W": bonk( Fore.WHITE , "W" ),
        "U": bonk( Fore.BLUE , "U" ),
        "B": bonk( Fore.LIGHTBLACK_EX , "B" ),
        "R": bonk( Fore.RED , "R" ),
        "G": bonk( Fore.GREEN , "G" ),
        "C": bonk( Fore. LIGHTWHITE_EX , "C" ),
    }   
    land_distro = {}
    for color in ["W", "U", "B", "R", "G", "C"]:
        color_label = color_map[color]
        count = color_count[color]
        pct = (count / total) * 100
        if color != "C":
            land_distro[color] = (pct / 100) * landcount
        percentages[color] = (pct / 100) * landcount
        print(f"  {color_label}: {pct:.2f}% ({count})")
    # Round and adjust so that the sum matches landcount
    rounded = {k: int(v) for k, v in land_distro.items()}
    remainder = landcount - sum(rounded.values())
    fractional = sorted(((k, land_distro[k] - rounded[k]) for k in rounded), key=lambda x: x[1], reverse=True)
    if fractional:
        for i in range(remainder):
            if i < len(fractional):
                rounded[fractional[i][0]] += 1

    print(Fore.YELLOW + "\nSummary Table Per Color:" + Style.RESET_ALL)
    print("-" * 80)
    print(f"{'Color':<8} | {'# Cards':<10} | {'# Producers':<15} | {'% Produce':<15} | {'% of Total':<15} | {'% diff':<15}")
    print("-" * 80)
    for color in ["W", "U", "B", "R", "G", "C"]:
        count = color_count[color]
        producers = len(producer_cards[color])
        pct_produce = (producers / total * 100) if total > 0 else 0
        pct_total = (count / total * 100) if total > 0 else 0
        symbol = color_map[color]
        diff = pct_produce - pct_total ;
        print(f"{symbol} | {count:<17} | {producers:<15} | {pct_produce:<15.2f} | {pct_total:<15.2f} | {diff:<15.2f}")
    print("-" * 80)

    print(Fore.GREEN + f"\nRecommended Land Distribution for {landcount} lands:"+ Style.RESET_ALL)
    for color in ["W", "U", "B", "R", "G"]:
        color_label = color_map[color]
        print(f"  {color_map[color]}: {rounded[color]} lands")

    print(Fore.MAGENTA + "\nProduce Mana:"+ Style.RESET_ALL)

    combined_set = set(item for lst in producer_cards.values() for item in lst)

    ansi_strip = re.compile(r'\x1b\[[0-9;]*m')

    def visible_len(s):
        return len(ansi_strip.sub('', s))

    def pad_ansi(s, width):
        padding = width - visible_len(s)
        return s + ' ' * max(0, padding)

    def truncate(s, maxlen=30):
        return s if len(s) <= maxlen else s[:27] + "..."
    
    def pad_ansi_right(s, width):
        padding = width - visible_len(s)
        return ' ' * max(0, padding) + s

    def format_symbols(produced_list):
        ordered = ['W', 'U', 'B', 'R', 'G', 'C']
        output = []
        for color in ordered:
            if color in produced_list:
                sym = bonk(color_map2[color], f"({color})")
                padded = f"{sym:<5}"  # ensure 5-character field even with ANSI
            else:
                padded = " " * 3
            output.append(padded)
        return "".join(output)


    print("-" * 100)
    print(f"{'Name':<30} | {'Typ':<16} | {'CMC':<5} | {'Symbols'}")
    print("-" * 100)

    for name in sorted(combined_set):
        data = load_or_fetch_card(name)
        if not data:
            continue

        produced = data.get("produced_mana", [])
        symbols = format_symbols(produced)
        cm = int(data.get("cmc", 0))
        short_name = truncate(name)
    
        # Get main card type
        type_line = data.get("type_line", "").split(" — ")[0]
        main_type = type_line.split()[0].capitalize() if type_line else ""

        print(f"{short_name:<30} | {main_type:<16} | {cm:<5} | {symbols}")

    print("-" * 100)








    print(Fore.YELLOW + "\nCard Category Table (All Cards):" + Style.RESET_ALL)

    # Preprocess formatted costs
    formatted_costs = {}
    max_cost_len = 0
    for raw_name in card_names:
        data = load_or_fetch_card(raw_name)
        if not data:
            continue
        raw = data.get("mana_cost", "")
        fmt = format_mana_cost(raw, {
            "W": Fore.WHITE + "W" + Style.RESET_ALL,
            "U": Fore.BLUE + "U" + Style.RESET_ALL,
            "B": Fore.LIGHTBLACK_EX + "B" + Style.RESET_ALL,
            "R": Fore.RED + "R" + Style.RESET_ALL,
            "G": Fore.GREEN + "G" + Style.RESET_ALL,
            "C": Fore.LIGHTWHITE_EX + "C" + Style.RESET_ALL,
        })
        formatted_costs[raw_name] = fmt
        max_cost_len = max(max_cost_len, visible_len(fmt))

    # Adjust headers
    categories = {
        "Damage": set(damage_cards),
        "Removal": set(removal_cards),
        "Draw": set(draw_cards),
        "Discard": set(discard_cards),
        "Mill": set(mill_cards),
        "Search": set(search_cards),
        "Heal": set(heal_cards),
        "Combo": set(combo_cards),
        "Tokens": set(token_cards),
        "Graveyard": set(graveyard_cards),
    }
    headers = ["Name", "Cost", "Type"] + list(categories.keys())
    col_widths = [30, max_cost_len, 12] + [10] * len(categories)

    # Header
    header_row = " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths))
    print("-" * len(header_row))
    print(header_row)
    print("-" * len(header_row))

    # Card data
    type_lookup = {name: t.capitalize() for t, names in type_cards.items() for name in names}
    cmc_lookup = dict(cmc_list)
    category_counts = {k: 0 for k in categories}

    for raw_name in sorted(card_names):
        data = load_or_fetch_card(raw_name)
        if not data:
            continue
        name = data.get("name", raw_name)
        typ = type_lookup.get(name, "")
        cost_fmt = pad_ansi_right(formatted_costs.get(raw_name, ""), max_cost_len)
        row = [f"{name:<30}", f"{cost_fmt}", f"{typ:<12}"]

        for key in categories:
            if name in categories[key]:
                row.append("✓".ljust(10))
                category_counts[key] += 1
            else:
                row.append(" ".ljust(10))
        print(" | ".join(row))

    # Summary
    print("-" * len(header_row))
    total_row = ["Total".ljust(30), "".ljust(max_cost_len), "".ljust(12)]
    for key in categories:
        total_row.append(str(category_counts[key]).ljust(10))
    print(" | ".join(total_row))
    print("-" * len(header_row))

   
    all_typed = []
    for t in sorted(type_cards.keys()):
        for name in sorted(type_cards[t]):
            cmc = next((c for n, c in cmc_list if n == name), 0)
            all_typed.append((name, t.capitalize(), cmc))
    total_cards = len(all_typed)














    print(Fore.YELLOW + "CMC Distribution:" + Style.RESET_ALL)

    cmc_distribution = defaultdict(int)
    for name,_, cmc in all_typed:
        cmc_distribution[int(cmc)] += 1

    for cmc in sorted(cmc_distribution):
        count = cmc_distribution[cmc]
        percent = (count / total_cards) * 100 if total_cards else 0
        print(f"  CMC {cmc:<2}: {count:<3} card(s) | {percent:>5.2f}%")


def read_card_list(path):
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


# ========== LOG OUTPUT TO FILE ==========


class TeeLogger:
    def __init__(self, filepath):
        self.terminal = sys.__stdout__
        self.log = open(filepath, "w", encoding="utf-8", buffering=1)
        self.ansi_escape = re.compile(r'\x1b\[[0-9;]*m')

    def write(self, message):
        self.terminal.write(message)
        clean = self.ansi_escape.sub('', message)
        self.log.write(clean)

    def flush(self):
        self.terminal.flush()
        self.log.flush()


log_file_path = "./output/analysis.txt"
sys.stdout = sys.stderr = TeeLogger(log_file_path)
print(f"[LOGGING] Console output will also be written to: {log_file_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python analyze.py <path to card_list.txt> <landcount>")
        sys.exit(1)

    card_list = read_card_list(sys.argv[1])
    try:
        landcount = int(sys.argv[2])
    except ValueError:
        print("Land count must be an integer.")
        sys.exit(1)

    analyze_mana_distribution(card_list, landcount)
    simulate_opening_hands(card_list)
