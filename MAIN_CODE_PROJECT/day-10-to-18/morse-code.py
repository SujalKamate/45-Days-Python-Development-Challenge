"""
Morse Code Encoder and Decoder with Full Punctuation Support
Encodes English to Morse, decodes Morse to English, handles invalid sequences.
"""

import re

MORSE_TABLE = {
    'A': '.-',   'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.',
    'F': '..-.', 'G': '--.',  'H': '....', 'I': '..',  'J': '.---',
    'K': '-.-',  'L': '.-..', 'M': '--',   'N': '-.',  'O': '---',
    'P': '.--.', 'Q': '--.-', 'R': '.-.',  'S': '...', 'T': '-',
    'U': '..-',  'V': '...-', 'W': '.--',  'X': '-..-','Y': '-.--',
    'Z': '--..',
    '0': '-----','1': '.----','2': '..---','3': '...--','4': '....-',
    '5': '.....','6': '-....','7': '--...','8': '---..','9': '----.',
    '.': '.-.-.-',',': '--..--','?': '..--..','!': '-.-.--',
    "'": '.----.','(': '-.--.', ')': '-.--.-','&': '.-...',
    ':': '---...', ';': '-.-.-.', '=': '-...-', '+': '.-.-.',
    '-': '-....-', '_': '..--.-', '"': '.-..-.', '$': '...-..-',
    '@': '.--.-.', ' ': '/',
}

REVERSE_TABLE = {v: k for k, v in MORSE_TABLE.items()}


def encode(text):
    """Convert plain text to Morse code."""
    text = text.upper()
    result = []
    unknown = []
    for ch in text:
        if ch in MORSE_TABLE:
            result.append(MORSE_TABLE[ch])
        else:
            result.append('?')
            unknown.append(ch)
    return ' '.join(result), unknown


def decode(morse):
    """Convert Morse code to plain text."""
    morse = morse.strip()
    words = morse.split(' / ')
    result = []
    errors = []

    for word in words:
        letters = word.strip().split(' ')
        decoded_word = []
        for code in letters:
            code = code.strip()
            if not code:
                continue
            if code in REVERSE_TABLE:
                decoded_word.append(REVERSE_TABLE[code])
            elif code == '?':
                decoded_word.append('?')
            else:
                decoded_word.append(f'[?:{code}]')
                errors.append(code)
        result.append(''.join(decoded_word))

    return ' '.join(result), errors


def morse_to_audio_representation(morse):
    """Represent Morse as dot/dash durations (unit-based)."""
    units = []
    for ch in morse:
        if ch == '.':
            units.append('· ')
        elif ch == '-':
            units.append('— ')
        elif ch == ' ':
            units.append('  ')
        elif ch == '/':
            units.append(' | ')
    return ''.join(units)


def morse_chart():
    """Print a formatted Morse code reference chart."""
    print(f"\n  {'═'*70}")
    print(f"  {'MORSE CODE REFERENCE CHART':^68}")
    print(f"  {'═'*70}")

    letters = [(ch, code) for ch, code in MORSE_TABLE.items() if ch.isalpha()]
    letters.sort()
    cols = 4
    rows = [letters[i:i+cols] for i in range(0, len(letters), cols)]
    for row in rows:
        line = "  "
        for ch, code in row:
            bar = ''
            for c in code:
                bar += '·' if c == '.' else '—'
            line += f"{ch}: {code:<8}({bar:<7})  "
        print(line)

    print(f"\n  {'─'*70}")
    nums = [(ch, code) for ch, code in MORSE_TABLE.items() if ch.isdigit()]
    nums.sort()
    print("  Numbers:")
    line = "  "
    for ch, code in nums:
        line += f"{ch}: {code:<8}  "
    print(line)

    print(f"\n  {'─'*70}")
    puncts = [(ch, code) for ch, code in MORSE_TABLE.items() if not ch.isalnum() and ch != ' ']
    print("  Punctuation:")
    for i in range(0, len(puncts), 4):
        row = puncts[i:i+4]
        line = "  "
        for ch, code in row:
            line += f"'{ch}': {code:<10}  "
        print(line)
    print(f"  {'═'*70}\n")


def interactive_translate():
    while True:
        print("\n  [1] Text → Morse  [2] Morse → Text  [3] Chart  [4] Back")
        choice = input("  Choice: ").strip()
        if choice == '4':
            break
        elif choice == '1':
            text = input("  Enter text: ")
            morse, unknown = encode(text)
            print(f"\n  Morse Code:")
            print(f"  {morse}")
            print(f"\n  Audio rep:")
            print(f"  {morse_to_audio_representation(morse)}")
            if unknown:
                print(f"  ⚠  Skipped characters: {unknown}")
        elif choice == '2':
            print("  Enter Morse code (use '/' for word breaks):")
            morse = input("  Morse: ")
            text, errors = decode(morse)
            print(f"\n  Decoded: {text}")
            if errors:
                print(f"  ⚠  Unknown sequences: {errors}")
        elif choice == '3':
            morse_chart()


def demo():
    test_cases = [
        "Hello World",
        "SOS",
        "Python 3.12",
        "MORSE CODE IS FUN!",
        "I love programming.",
    ]

    print(f"\n  {'═'*65}")
    print(f"  ENCODING DEMO")
    print(f"  {'═'*65}")
    for text in test_cases:
        morse, _ = encode(text)
        decoded, _ = decode(morse)
        print(f"\n  Original : {text}")
        print(f"  Morse    : {morse[:80]}{'...' if len(morse) > 80 else ''}")
        print(f"  Decoded  : {decoded}")
        match = decoded.upper() == text.upper()
        print(f"  Round-trip: {'✓ Match' if match else '✗ Mismatch'}")

    print(f"\n  {'═'*65}")
    print(f"  DECODE KNOWN MORSE")
    print(f"  {'═'*65}")
    known = [
        ("... --- ...", "SOS"),
        (".... . .-.. .-.. ---", "HELLO"),
        ("-.- . . .--.  -.-. --- -.. .. -. --.", "KEEP CODING"),
    ]
    for morse, expected in known:
        decoded, errs = decode(morse)
        icon = "✓" if decoded.strip() == expected else "✗"
        print(f"  {icon} '{morse}' → '{decoded}' (expected: '{expected}')")

    # Error handling
    print(f"\n  Error Handling:")
    bad_morse, errors = decode("... --- ...-.-.- ??? .-.-.-")
    print(f"  Input : '... --- ...-.-.- ??? .-.-.-'")
    print(f"  Output: '{bad_morse}'")
    if errors:
        print(f"  Errors: {errors}")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Morse Code Encoder/Decoder v1.0       ║")
    print("╚══════════════════════════════════════════╝")

    demo()
    morse_chart()
    interactive_translate()

    print("  Goodbye!")


if __name__ == "__main__":
    main()
