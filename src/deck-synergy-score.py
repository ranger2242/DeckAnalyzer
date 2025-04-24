
import os
import sys
import json
import re
import numpy as np
from collections import defaultdict, Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def safe_card_filename(card_name):
    return card_name.lower().replace(" ", "_").replace("/", "-")

def format_card_name(name):
    name = name.lower()
    name = re.sub(r"[^\w\s-]", "", name)
    return name.replace(" ", "-")

def load_scryfall(card_name, folder="./scryfall-data"):
    path = os.path.join(folder, f"{safe_card_filename(card_name)}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return None

def load_edhrec_synergy(card_name, folder="./edhrec-card-data"):
    formatted = format_card_name(card_name)
    path = os.path.join(folder, f"{formatted}_synergy.csv")
    if not os.path.exists(path):
        return []
    synergies = []
    with open(path, "r", encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.strip().split(",", 1)
            if len(parts) == 2:
                try:
                    score = int(parts[1])
                    if score > 0:
                        synergies.append(score)
                except:
                    continue
    return synergies

def clean_features(card):
    fields = []
    fields.append(card.get("type_line", ""))
    fields.append(" ".join(card.get("colors", [])))
    fields.append(" ".join(card.get("produced_mana", [])))
    fields.append(" ".join(card.get("keywords", [])))
    fields.append(card.get("oracle_text", ""))
    fields.append(f"cmc:{card.get('cmc', '')}")
    fields.append(f"power:{card.get('power', '')}")
    fields.append(f"toughness:{card.get('toughness', '')}")
    fields.append(f"loyalty:{card.get('loyalty', '')}")
    return " ".join(str(x).lower() for x in fields)

def get_card_type(card):
    type_line = card.get("type_line", "").lower()
    for t in ["creature", "sorcery", "instant", "artifact", "enchantment", "planeswalker", "land"]:
        if t in type_line:
            return t
    return "unknown"

def detect_tribes(card):
    type_line = card.get("type_line", "").lower()
    creature_types = [
        "dragon", "elf", "goblin", "zombie", "vampire", "angel", "human", "merfolk", "wizard", "beast",
        "elemental", "demon", "soldier", "warrior", "shaman", "druid", "sliver", "cat", "bird", "knight"
    ]
    return [tribe for tribe in creature_types if tribe in type_line]

def combined_synergy_score(input_file):
    with open(input_file, "r", encoding="utf-8") as f:
        input_names = [line.strip() for line in f if line.strip()]

    documents = []
    index_map = {}
    card_types = {}
    edhrec_scores = {}
    color_curve = Counter()
    tribe_counter = Counter()
    failed_names = []

    for idx, name in enumerate(input_names):
        data = load_scryfall(name)
        edh_synergy = load_edhrec_synergy(name)
        edhrec_scores[name] = round(np.mean(edh_synergy), 2) if edh_synergy else 0.0

        if data and "card_faces" not in data:
            documents.append(clean_features(data))
            index_map[name] = len(documents) - 1
            card_types[name] = get_card_type(data)

            # Count tribal info
            for tribe in detect_tribes(data):
                tribe_counter[tribe] += 1

            # Count color curve
            for color in data.get("colors", []):
                color_curve[color] += 1
        else:
            failed_names.append(name)
            card_types[name] = "unknown"

    vector_scores = {name: 0.0 for name in input_names}

    if documents:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform(documents)
        sim_matrix = cosine_similarity(tfidf_matrix)
        np.fill_diagonal(sim_matrix, 0)

        for name, i in index_map.items():
            vector_scores[name] = round(sim_matrix[i].mean() * 100, 2)

    combined = {name: round(0.6 * vector_scores[name] + 0.4 * edhrec_scores[name], 2) for name in input_names}

    grouped = defaultdict(list)
    for name in input_names:
        grouped[card_types[name]].append((name, combined[name]))

    os.makedirs("./output", exist_ok=True)
    output_path = "./output/deck-synergy.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        for group in sorted(grouped.keys()):
            f.write(f"## {group.upper()} ({len(grouped[group])})\n")
            for name, score in sorted(grouped[group], key=lambda x: x[1], reverse=True):
                f.write(f"{name}: {score}\n")
            f.write("\n")

        f.write(f"### TOTAL CARDS: {len(input_names)}\n")
        f.write("\n")
        f.write("### COLOR DISTRIBUTION:\n")
        for color, count in sorted(color_curve.items()):
            f.write(f"{color.upper()}: {count}\n")
        f.write("\n")
        f.write("### TRIBAL DISTRIBUTION:\n")
        for tribe, count in tribe_counter.most_common():
            f.write(f"{tribe.capitalize()}: {count}\n")

    print(f"✅ Extended synergy score (with tribe and color curve) saved to: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python combined_synergy_score.py <deck_list.txt>")
        sys.exit(1)
    combined_synergy_score(sys.argv[1])
