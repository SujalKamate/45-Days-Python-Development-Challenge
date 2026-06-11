"""
Randomized Quiz Application with Scoring, Timing and Answer Explanations
Loads questions from embedded data, randomizes MCQs, tracks score and time, shows summary.
"""

import random
import time
from datetime import datetime

QUESTIONS = [
    {
        "question": "What does CPU stand for?",
        "options": ["Central Processing Unit", "Computer Personal Unit", "Central Program Utility", "Central Peripheral Unit"],
        "answer": 0,
        "explanation": "CPU stands for Central Processing Unit — the brain of a computer that executes instructions."
    },
    {
        "question": "Which language is known as the 'mother of all languages'?",
        "options": ["C", "Assembly", "Fortran", "COBOL"],
        "answer": 0,
        "explanation": "C is often called the mother of modern programming languages; many languages derive from it."
    },
    {
        "question": "What is the time complexity of Binary Search?",
        "options": ["O(n)", "O(log n)", "O(n²)", "O(1)"],
        "answer": 1,
        "explanation": "Binary search halves the search space each step, giving O(log n) complexity."
    },
    {
        "question": "Which data structure uses LIFO order?",
        "options": ["Queue", "Stack", "Linked List", "Tree"],
        "answer": 1,
        "explanation": "A Stack uses Last-In-First-Out (LIFO) — the last element pushed is the first popped."
    },
    {
        "question": "What is the output of: print(type(3.0))?",
        "options": ["<class 'int'>", "<class 'float'>", "<class 'double'>", "<class 'number'>"],
        "answer": 1,
        "explanation": "3.0 is a floating-point literal, so type(3.0) returns <class 'float'>."
    },
    {
        "question": "Which HTTP method is used to retrieve data?",
        "options": ["POST", "PUT", "GET", "DELETE"],
        "answer": 2,
        "explanation": "GET is used to retrieve data from a server. POST is for submitting data."
    },
    {
        "question": "What does SQL stand for?",
        "options": ["Structured Query Language", "Simple Query Logic", "Server Query Language", "Standard Query List"],
        "answer": 0,
        "explanation": "SQL stands for Structured Query Language, used to manage relational databases."
    },
    {
        "question": "Which sorting algorithm has O(n log n) average time complexity?",
        "options": ["Bubble Sort", "Insertion Sort", "Merge Sort", "Selection Sort"],
        "answer": 2,
        "explanation": "Merge Sort consistently achieves O(n log n) time via divide-and-conquer."
    },
    {
        "question": "In Python, what does 'list comprehension' look like?",
        "options": ["(x for x in lst)", "[x for x in lst]", "{x for x in lst}", "list(x for x in lst)"],
        "answer": 1,
        "explanation": "[x for x in lst] is list comprehension. () gives a generator, {} gives a set."
    },
    {
        "question": "What is 2 ** 10 in Python?",
        "options": ["20", "100", "1024", "512"],
        "answer": 2,
        "explanation": "** is the exponentiation operator. 2**10 = 1024."
    },
    {
        "question": "Which protocol is used for secure web browsing?",
        "options": ["HTTP", "FTP", "HTTPS", "SMTP"],
        "answer": 2,
        "explanation": "HTTPS (HyperText Transfer Protocol Secure) encrypts web traffic using TLS/SSL."
    },
    {
        "question": "What is a 'deadlock' in operating systems?",
        "options": ["A slow process", "Two processes waiting on each other forever", "A crashed program", "Memory overflow"],
        "answer": 1,
        "explanation": "Deadlock occurs when two or more processes are each waiting for the other to release a resource."
    },
    {
        "question": "Which keyword is used to define a function in Python?",
        "options": ["func", "define", "def", "function"],
        "answer": 2,
        "explanation": "In Python, 'def' keyword is used to define a function."
    },
    {
        "question": "What does OOP stand for?",
        "options": ["Object-Oriented Programming", "Operational Output Processing", "Online Object Protocol", "Ordered Object Parsing"],
        "answer": 0,
        "explanation": "OOP stands for Object-Oriented Programming, a paradigm based on objects and classes."
    },
    {
        "question": "What is the default port for HTTP?",
        "options": ["443", "22", "80", "8080"],
        "answer": 2,
        "explanation": "HTTP uses port 80 by default. HTTPS uses port 443."
    },
]


def run_quiz(num_questions=10):
    questions = random.sample(QUESTIONS, min(num_questions, len(QUESTIONS)))
    score = 0
    results = []
    total_time = 0

    print(f"\n  {'═'*60}")
    print(f"  QUIZ — {num_questions} Questions | Timer per question")
    print(f"  {'═'*60}\n")

    for i, q in enumerate(questions, 1):
        opts = list(enumerate(q['options']))
        random.shuffle(opts)
        shuffled_opts = [o for _, o in opts]
        correct_new_idx = next(j for j, (orig, _) in enumerate(opts) if orig == q['answer'])

        print(f"  Q{i}/{num_questions}: {q['question']}")
        for j, opt in enumerate(shuffled_opts):
            print(f"    {chr(65+j)}) {opt}")

        start = time.time()
        raw = input("  Your answer (A/B/C/D): ").strip().upper()
        elapsed = round(time.time() - start, 2)
        total_time += elapsed

        letter_map = {chr(65+j): j for j in range(len(shuffled_opts))}
        user_idx = letter_map.get(raw, -1)
        correct = user_idx == correct_new_idx

        if correct:
            score += 1
            print(f"  ✓ Correct! ({elapsed:.1f}s)")
        else:
            correct_letter = chr(65 + correct_new_idx)
            print(f"  ✗ Wrong. Correct: {correct_letter}) {shuffled_opts[correct_new_idx]}")

        print(f"  💡 {q['explanation']}\n")

        results.append({
            'question': q['question'],
            'correct': correct,
            'time': elapsed,
            'explanation': q['explanation'],
        })

    return score, len(questions), total_time, results


def print_summary(score, total, total_time, results):
    pct = score / total * 100 if total else 0
    avg_time = total_time / total if total else 0

    print(f"\n  {'═'*60}")
    print(f"  QUIZ SUMMARY — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  {'═'*60}")
    print(f"  Score       : {score}/{total} ({pct:.1f}%)")
    print(f"  Total Time  : {total_time:.1f}s  |  Avg per Q: {avg_time:.1f}s")

    grade_map = [(90, 'A+', '🏆'), (80, 'A', '🥇'), (70, 'B', '🥈'),
                 (60, 'C', '🥉'), (50, 'D', '😐'), (0, 'F', '📚')]
    grade, icon = next((g, ic) for th, g, ic in grade_map if pct >= th), ''
    for th, g, ic in grade_map:
        if pct >= th:
            grade, icon = g, ic
            break

    print(f"  Grade       : {grade} {icon}")
    print(f"\n  {'─'*60}")
    print(f"  {'#':<4} {'Result':<8} {'Time':>6}  Question")
    print(f"  {'─'*60}")
    for i, r in enumerate(results, 1):
        status = '✓' if r['correct'] else '✗'
        print(f"  {i:<4} {status:<8} {r['time']:>5.1f}s  {r['question'][:45]}")

    wrong = [r for r in results if not r['correct']]
    if wrong:
        print(f"\n  Review ({len(wrong)} incorrect):")
        for r in wrong:
            print(f"    ✗ {r['question']}")
            print(f"      💡 {r['explanation']}")
    print(f"  {'═'*60}\n")


def main():
    print("╔══════════════════════════════════════════╗")
    print("║   Randomized Quiz Application v1.0      ║")
    print("╚══════════════════════════════════════════╝")
    print(f"  Total available questions: {len(QUESTIONS)}")

    while True:
        try:
            n = int(input(f"\n  How many questions? (1-{len(QUESTIONS)}): ") or "10")
            n = max(1, min(n, len(QUESTIONS)))
            break
        except ValueError:
            print("  Please enter a number.")

    score, total, total_time, results = run_quiz(n)
    print_summary(score, total, total_time, results)

    again = input("  Play again? (y/n): ").strip().lower()
    if again == 'y':
        main()


if __name__ == "__main__":
    main()
