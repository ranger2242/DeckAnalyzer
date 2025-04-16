import re
import sys
import os

def extract_card_names(file_path):
    card_names = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            match = re.match(r'^\d+\s+(.+?)\s+\(.*\)$', line)
            if match:
                card_names.append(match.group(1))
    return card_names

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python extract_cards.py <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = "./output/converted.txt"

    cards = extract_card_names(input_file)

    with open(output_file, 'w', encoding='utf-8') as f:
        for card in cards:
            f.write(card + '\n')

    print(f"✅ Saved {len(cards)} card names to '{output_file}'.")
