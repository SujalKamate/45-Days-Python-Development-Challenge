"""
Caesar Cipher and ROT13 Encoder-Decoder with Brute Force Analysis
Supports customizable shift, full sentence encoding, and brute-force display.
"""

import string


def caesar_encode(text, shift):
    """Encode text using Caesar cipher with given shift."""
    shift = shift % 26
    result = []
    for ch in text:
        if ch.isalpha():
            base = ord('A') if ch.isupper() else ord('a')
            result.append(chr((ord(ch) - base + shift) % 26 + base))
        else:
            result.append(ch)
    return ''.join(result)


def caesar_decode(text, shift):
    """Decode Caesar cipher — equivalent to encoding with negative shift."""
    return caesar_encode(text, -shift)


def rot13(text):
    """ROT13 is Caesar with shift=13 and is its own inverse."""
    return caesar_encode(text, 13)


def brute_force(cipher_text):
    """Try all 25 possible Caesar shifts and display results."""
    print(f"\n  Brute Force Analysis for: \"{cipher_text}\"")
    print(f"  {'─'*65}")
    print(f"  {'Shift':<8} {'Decoded Text'}")
    print(f"  {'─'*65}")
    for shift in range(1, 26):
        decoded = caesar_decode(cipher_text, shift)
        print(f"  {shift:<8} {decoded}")
    print(f"  {'─'*65}")


def frequency_analysis(text):
    """Compute letter frequency for cryptanalysis hints."""
    letters = [ch.lower() for ch in text if ch.isalpha()]
    total = len(letters)
    if total == 0:
        return {}
    freq = {}
    for ch in letters:
        freq[ch] = freq.get(ch, 0) + 1
    sorted_freq = sorted(freq.items(), key=lambda x: -x[1])
    return [(ch, count, round(count / total * 100, 1)) for ch, count, _ in
            [(ch, count, count / total) for ch, count in sorted_freq]]


def print_frequency_table(text):
    """Display frequency analysis for cipher text."""
    data = frequency_analysis(text)
    if not data:
        print("  No alphabetic characters to analyze.")
        return
    print(f"\n  Letter Frequency Analysis:")
    print(f"  {'Letter':<10} {'Count':<8} {'Percent'}")
    print(f"  {'─'*30}")
    for ch, count, pct in data[:10]:
        bar = '█' * int(pct / 2)
        print(f"  {ch.upper():<10} {count:<8} {pct:>5}%  {bar}")


def vigenere_encode(text, key):
    """Vigenere cipher for bonus functionality."""
    key = key.lower()
    result = []
    key_idx = 0
    for ch in text:
        if ch.isalpha():
            shift = ord(key[key_idx % len(key)]) - ord('a')
            base = ord('A') if ch.isupper() else ord('a')
            result.append(chr((ord(ch) - base + shift) % 26 + base))
            key_idx += 1
        else:
            result.append(ch)
    return ''.join(result)


def vigenere_decode(text, key):
    key = key.lower()
    result = []
    key_idx = 0
    for ch in text:
        if ch.isalpha():
            shift = ord(key[key_idx % len(key)]) - ord('a')
            base = ord('A') if ch.isupper() else ord('a')
            result.append(chr((ord(ch) - base - shift) % 26 + base))
            key_idx += 1
        else:
            result.append(ch)
    return ''.join(result)


def demo():
    print("\n  ── Caesar Cipher Demo ──")
    samples = [
        ("Hello, World!", 3),
        ("Python Programming is fun!", 13),
        ("The Quick Brown Fox.", 7),
    ]
    for text, shift in samples:
        encoded = caesar_encode(text, shift)
        decoded = caesar_decode(encoded, shift)
        print(f"\n  Original : {text}")
        print(f"  Shift    : {shift}")
        print(f"  Encoded  : {encoded}")
        print(f"  Decoded  : {decoded}")
        print(f"  ROT13    : {rot13(text)}")

    print("\n  ── Brute Force Demo ──")
    cipher = caesar_encode("Secret Message", 11)
    print(f"  Cipher text (shift=11): {cipher}")
    brute_force(cipher)
    print_frequency_table(cipher)

    print("\n  ── Vigenere Demo ──")
    msg = "Attack at dawn"
    key = "LEMON"
    enc = vigenere_encode(msg, key)
    dec = vigenere_decode(enc, key)
    print(f"  Message  : {msg}")
    print(f"  Key      : {key}")
    print(f"  Encoded  : {enc}")
    print(f"  Decoded  : {dec}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Caesar Cipher & ROT13 Toolkit v1.0     ║")
    print("╚══════════════════════════════════════════╝")
    demo()

    print("\n  ── Interactive Mode ──")
    while True:
        print("\n  [1] Encode  [2] Decode  [3] ROT13  [4] Brute Force  [5] Quit")
        choice = input("  Choice: ").strip()
        if choice == '5':
            break
        text = input("  Enter text: ")
        if choice in ('1', '2'):
            try:
                shift = int(input("  Shift (0-25): "))
            except ValueError:
                print("  Invalid shift."); continue
            if choice == '1':
                print(f"  Encoded: {caesar_encode(text, shift)}")
            else:
                print(f"  Decoded: {caesar_decode(text, shift)}")
        elif choice == '3':
            print(f"  ROT13: {rot13(text)}")
        elif choice == '4':
            brute_force(text)
        else:
            print("  Invalid choice.")


if __name__ == "__main__":
    main()
