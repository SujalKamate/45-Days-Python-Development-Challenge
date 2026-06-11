"""
Run-Length Encoding Text Compression with Ratio Analysis and Edge Handling
Implements RLE encode/decode, compression ratio, handles all edge cases.
"""

import re
import random
import string
import time


def rle_encode(text):
    """
    Encode a string using Run-Length Encoding.
    Consecutive repeated characters are replaced by count+char.
    Single characters are stored as-is (no '1' prefix).
    """
    if not text:
        return "", []

    encoded_parts = []
    trace = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        count = 1
        while i + count < n and text[i + count] == ch:
            count += 1
        if count > 1:
            encoded_parts.append(f"{count}{ch}")
            trace.append((ch, count, f"{count}{ch}"))
        else:
            encoded_parts.append(ch)
            trace.append((ch, 1, ch))
        i += count

    return "".join(encoded_parts), trace


def rle_decode(encoded):
    """
    Decode an RLE-encoded string.
    Handles patterns like '4A', 'B', '12C', etc.
    """
    if not encoded:
        return "", []

    result = []
    trace  = []
    i = 0
    n = len(encoded)

    while i < n:
        # Collect digit run
        count_str = ""
        while i < n and encoded[i].isdigit():
            count_str += encoded[i]
            i += 1
        if i >= n:
            if count_str:
                raise ValueError(f"Trailing digits '{count_str}' with no character.")
            break
        ch = encoded[i]
        i += 1
        count = int(count_str) if count_str else 1
        result.append(ch * count)
        trace.append((count, ch, ch * count))

    return "".join(result), trace


def compression_ratio(original, compressed):
    orig_len = len(original)
    comp_len = len(compressed)
    if orig_len == 0:
        return 0.0, 0.0
    ratio  = comp_len / orig_len
    saving = (1 - ratio) * 100
    return round(ratio, 4), round(saving, 2)


def is_beneficial(original, encoded):
    return len(encoded) < len(original)


def rle_encode_binary(data: bytes) -> list:
    """RLE on raw bytes — returns list of (count, byte_value) tuples."""
    if not data:
        return []
    result = []
    i = 0
    while i < len(data):
        b = data[i]
        count = 1
        while i + count < len(data) and data[i + count] == b and count < 255:
            count += 1
        result.append((count, b))
        i += count
    return result


def rle_decode_binary(pairs: list) -> bytes:
    return bytes(b for count, b in pairs for b in [b] * count)


def generate_test_strings():
    return {
        "All same":         "AAAAAAAAAAAAAAAAAAAAAA",
        "No repeats":       "ABCDEFGHIJKLMNOPQRSTUVWX",
        "Mixed short":      "AABBBCCCCDDDDDEEEEEEF",
        "Long repeats":     "AAABBBBBBBBBCCCCCCCCCCCCC",
        "Single chars":     "A",
        "Two chars":        "AB",
        "Empty":            "",
        "Sentence":         "AAABBBCCCCDDDEEEFFFGGG",
        "DNA sequence":     "AATTTCCCGGGATTTAAACCC",
        "Random":           "".join(random.choices("ABCD", weights=[4,3,2,1], k=40)),
        "Digits/symbols":   "111222333!!!???!!!",
        "Real text":        "MISSISSIPPI RIVER",
    }


def print_trace(trace, label="Trace"):
    if not trace:
        return
    print(f"\n  {label}:")
    for item in trace[:10]:
        if len(item) == 3 and isinstance(item[0], str):
            ch, count, enc = item
            print(f"    '{ch}' × {count} → '{enc}'")
        else:
            count, ch, dec = item
            print(f"    '{count}' × '{ch}' → '{dec}'")
    if len(trace) > 10:
        print(f"    ... ({len(trace)-10} more steps)")


def print_analysis(label, original):
    if not original:
        print(f"  {label}: (empty string — no compression)")
        return
    encoded, enc_trace = rle_encode(original)
    decoded, dec_trace = rle_decode(encoded)
    ratio, saving = compression_ratio(original, encoded)
    match = decoded == original

    beneficial = is_beneficial(original, encoded)
    status = "✓ Compresses" if beneficial else "✗ Expands"

    print(f"\n  ── {label} ──")
    print(f"  Original  [{len(original):>4}]: {original[:60]}{'...' if len(original)>60 else ''}")
    print(f"  Encoded   [{len(encoded):>4}]: {encoded[:60]}{'...' if len(encoded)>60 else ''}")
    print(f"  Decoded   [{len(decoded):>4}]: {decoded[:60]}{'...' if len(decoded)>60 else ''}")
    print(f"  Ratio     : {ratio:.4f}  |  Saving: {saving:+.2f}%  |  {status}")
    print(f"  Round-trip: {'✓ Match' if match else '✗ MISMATCH!'}")


def benchmark(text, iterations=1000):
    start = time.perf_counter()
    for _ in range(iterations):
        enc, _ = rle_encode(text)
    enc_time = (time.perf_counter() - start) * 1000

    enc, _ = rle_encode(text)
    start = time.perf_counter()
    for _ in range(iterations):
        rle_decode(enc)
    dec_time = (time.perf_counter() - start) * 1000

    print(f"\n  Benchmark ({iterations} iterations, input len={len(text)}):")
    print(f"  Encode: {enc_time:.2f}ms total  ({enc_time/iterations:.4f}ms each)")
    print(f"  Decode: {dec_time:.2f}ms total  ({dec_time/iterations:.4f}ms each)")


def interactive():
    while True:
        print("\n  [1] Encode  [2] Decode  [3] Quit")
        choice = input("  Choice: ").strip()
        if choice == "3":
            break
        elif choice == "1":
            text = input("  Text to encode: ")
            enc, trace = rle_encode(text)
            ratio, saving = compression_ratio(text, enc)
            print(f"  Encoded : '{enc}'")
            print(f"  Ratio   : {ratio}  Saving: {saving:+.2f}%")
            print_trace(trace, "Encoding trace")
        elif choice == "2":
            enc = input("  RLE string to decode: ")
            try:
                dec, trace = rle_decode(enc)
                print(f"  Decoded : '{dec}'")
                print_trace(trace, "Decoding trace")
            except ValueError as e:
                print(f"  ✗ Error: {e}")
        else:
            print("  Invalid choice.")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Run-Length Encoding (RLE) v1.0        ║")
    print("╚══════════════════════════════════════════╝")

    tests = generate_test_strings()
    for label, text in tests.items():
        print_analysis(label, text)

    # Summary table
    print(f"\n  {'═'*60}")
    print(f"  COMPRESSION SUMMARY")
    print(f"  {'─'*60}")
    print(f"  {'Label':<22} {'Orig':>6} {'Enc':>6} {'Ratio':>8} {'Saving':>9}")
    print(f"  {'─'*60}")
    for label, text in tests.items():
        if not text:
            print(f"  {label:<22} {'':>6} {'':>6} {'N/A':>8} {'N/A':>9}")
            continue
        enc, _ = rle_encode(text)
        ratio, saving = compression_ratio(text, enc)
        symbol = "▼" if saving > 0 else "▲"
        print(f"  {label:<22} {len(text):>6} {len(enc):>6} {ratio:>8.4f} {saving:>+8.2f}% {symbol}")
    print(f"  {'═'*60}")

    # Binary demo
    print(f"\n  Binary RLE Demo:")
    binary_data = bytes([255]*10 + [0]*5 + [128]*8 + [64]*3)
    pairs = rle_encode_binary(binary_data)
    restored = rle_decode_binary(pairs)
    print(f"  Original bytes : {len(binary_data)}")
    print(f"  RLE pairs      : {len(pairs)}  {pairs[:5]}...")
    print(f"  Restored       : {'✓ Match' if restored == binary_data else '✗ Mismatch'}")

    # Benchmark
    big_text = "ABCD" * 500 + "AAAA" * 200 + "XYZ" * 100
    benchmark(big_text)

    interactive()


if __name__ == "__main__":
    main()
