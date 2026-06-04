import os
from pathlib import Path

src_dir = Path(r"C:\Users\risha\Documents\GitHub\45-Days-Python-Development-Challenge\MAIN_CODE_PROJECT\src")

boilerplate = """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'name': 'alpha', 'value': 1, 'active': True},
            {'name': 'beta', 'value': 2, 'active': False},
            {'name': 'gamma', 'value': 3, 'active': True},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        active = [item for item in items if item.get('active', False)]
        values = [item.get('value', 0) for item in active]
        return {
            'total_items': len(items),
            'active_items': len(active),
            'summary': self.summarize_list(values),
        }"""

replacements = {
    'api_response_parser.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'status_code': 200, 'body': '{"user": "alice", "role": "admin"}', 'headers': {'Content-Type': 'application/json'}},
            {'status_code': 404, 'body': '{"error": "Not Found"}', 'headers': {'Content-Type': 'application/json'}},
            {'status_code': 201, 'body': '{"status": "created"}', 'headers': {'Content-Type': 'application/json'}},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        parsed = []
        success_count = 0
        for item in items:
            status = item.get('status_code', 0)
            if 200 <= status < 300:
                success_count += 1
                try:
                    body_dict = json.loads(item.get('body', '{}'))
                    parsed.append(body_dict)
                except Exception:
                    pass
        return {
            'total_responses': len(items),
            'successful_responses': success_count,
            'parsed_bodies': parsed
        }""",

    'banking_simulation.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'type': 'deposit', 'amount': 1500.0, 'timestamp': '2026-05-29T10:00:00'},
            {'type': 'withdrawal', 'amount': 200.0, 'timestamp': '2026-05-29T10:15:00'},
            {'type': 'deposit', 'amount': 350.0, 'timestamp': '2026-05-29T10:30:00'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        balance = 0.0
        deposits = 0
        withdrawals = 0
        amounts = []
        for tx in items:
            amount = tx.get('amount', 0.0)
            amounts.append(amount)
            if tx.get('type') == 'deposit':
                balance += amount
                deposits += 1
            elif tx.get('type') == 'withdrawal':
                balance -= amount
                withdrawals += 1
        return {
            'transaction_count': len(items),
            'final_balance': round(balance, 2),
            'deposits': deposits,
            'withdrawals': withdrawals,
            'statistics': self.summarize_list(amounts)
        }""",

    'cli_calculator.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'operator': '+', 'operand1': 12, 'operand2': 8},
            {'operator': '*', 'operand1': 5, 'operand2': 6},
            {'operator': '/', 'operand1': 100, 'operand2': 4},
            {'operator': '/', 'operand1': 5, 'operand2': 0},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        errors = 0
        for calc in items:
            op = calc.get('operator')
            a = calc.get('operand1', 0)
            b = calc.get('operand2', 0)
            try:
                if op == '+':
                    results.append(a + b)
                elif op == '-':
                    results.append(a - b)
                elif op == '*':
                    results.append(a * b)
                elif op == '/':
                    if b == 0:
                        raise ZeroDivisionError('Division by zero')
                    results.append(a / b)
                else:
                    errors += 1
            except Exception:
                errors += 1
        return {
            'total_operations': len(items),
            'successful_operations': len(results),
            'errors': errors,
            'results': results,
            'statistics': self.summarize_list([float(r) for r in results])
        }""",

    'contact_manager.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'name': 'Alice Smith', 'phone': '123-456-7890', 'email': 'alice@example.com', 'category': 'Work'},
            {'name': 'Bob Jones', 'phone': '987-654-321', 'email': 'bob-at-example.com', 'category': 'Personal'},
            {'name': 'Charlie Brown', 'phone': '555-0199', 'email': 'charlie@gmail.com', 'category': 'Work'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import re
        valid_contacts = []
        invalid_contacts = []
        categories = {}
        for contact in items:
            email = contact.get('email', '')
            phone = contact.get('phone', '')
            name = contact.get('name', '')
            category = contact.get('category', 'Uncategorized')
            
            email_valid = bool(re.match(r"[^@]+@[^@]+\\.[^@]+", email))
            phone_valid = len(re.sub(r"\\D", "", phone)) >= 7
            
            if email_valid and phone_valid:
                valid_contacts.append(name)
                categories[category] = categories.get(category, 0) + 1
            else:
                invalid_contacts.append(name)
        return {
            'total_contacts': len(items),
            'valid_contacts': valid_contacts,
            'invalid_contacts': invalid_contacts,
            'category_counts': categories
        }""",

    'countdown_reminder.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'title': 'Python Challenge End', 'target_date': '2026-07-15T00:00:00'},
            {'title': 'Code Review Meeting', 'target_date': '2026-05-30T10:00:00'},
            {'title': 'Past Project Deadline', 'target_date': '2026-05-01T12:00:00'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        now = datetime.utcnow()
        events = []
        for item in items:
            title = item.get('title', 'Event')
            try:
                target = datetime.fromisoformat(item.get('target_date', ''))
                diff = target - now
                total_seconds = diff.total_seconds()
                events.append({
                    'title': title,
                    'seconds_remaining': round(total_seconds, 2),
                    'days_remaining': diff.days,
                    'status': 'upcoming' if total_seconds > 0 else 'past'
                })
            except Exception as e:
                events.append({'title': title, 'error': str(e)})
        return {
            'current_time': now.isoformat(),
            'total_events': len(items),
            'events_status': events
        }""",

    'credential_storage.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'username': 'user1', 'plaintext_password': 'SuperSecretPassword123'},
            {'username': 'admin', 'plaintext_password': 'admin_password_99'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import hashlib
        db_records = {}
        for cred in items:
            user = cred.get('username')
            pwd = cred.get('plaintext_password', '')
            if user:
                hashed = hashlib.sha256(pwd.encode('utf-8')).hexdigest()
                db_records[user] = hashed
        return {
            'records_created': len(db_records),
            'database_simulation': db_records
        }""",

    'csv_analysis.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'id': '101', 'category': 'Electronics', 'score': 95.5},
            {'id': '102', 'category': 'Clothing', 'score': 78.2},
            {'id': '103', 'category': 'Electronics', 'score': 88.0},
            {'id': '104', 'category': 'Clothing', 'score': 92.1},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        scores = [item.get('score', 0.0) for item in items]
        cats = {}
        for item in items:
            cat = item.get('category', 'Other')
            cats[cat] = cats.get(cat, []) + [item.get('score', 0.0)]
        
        category_summaries = {}
        for cat, val_list in cats.items():
            category_summaries[cat] = self.stats_from_numbers(val_list)
        return {
            'total_records': len(items),
            'overall_statistics': self.stats_from_numbers(scores),
            'category_breakdown': category_summaries
        }""",

    'currency_exchange.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'amount': 100.0, 'from_currency': 'USD', 'to_currency': 'EUR'},
            {'amount': 250.0, 'from_currency': 'GBP', 'to_currency': 'USD'},
            {'amount': 50.0, 'from_currency': 'EUR', 'to_currency': 'GBP'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        rates = {'USD': 1.0, 'EUR': 0.92, 'GBP': 0.79}
        results = []
        for req in items:
            amount = req.get('amount', 0.0)
            from_cur = req.get('from_currency')
            to_cur = req.get('to_currency')
            if from_cur in rates and to_cur in rates:
                usd_amount = amount / rates[from_cur]
                converted = usd_amount * rates[to_cur]
                results.append({
                    'amount': amount,
                    'from': from_cur,
                    'to': to_cur,
                    'converted_amount': round(converted, 4)
                })
        return {
            'requests_processed': len(items),
            'conversions': results
        }""",

    'data_visualization.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'label': 'A', 'value': 5.0},
            {'label': 'B', 'value': 12.0},
            {'label': 'C', 'value': 8.0},
            {'label': 'D', 'value': 3.0},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        max_val = max([item.get('value', 0.0) for item in items] or [1.0])
        chart_lines = []
        for item in items:
            label = item.get('label', '')
            val = item.get('value', 0.0)
            bar_len = int((val / max_val) * 20)
            bar = '#' * bar_len
            chart_lines.append(f'{label:<5} | {bar} ({val})')
        return {
            'data_points': len(items),
            'ascii_chart': '\\n'.join(chart_lines)
        }""",

    'datetime_utility.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'date_str': '2026-05-29 12:00:00', 'format': '%Y-%m-%d %H:%M:%S'},
            {'date_str': '2026-12-25 00:00:00', 'format': '%Y-%m-%d %H:%M:%S'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for item in items:
            date_str = item.get('date_str', '')
            fmt = item.get('format', '%Y-%m-%d %H:%M:%S')
            try:
                dt = datetime.strptime(date_str, fmt)
                results.append({
                    'parsed': dt.isoformat(),
                    'rfc2822': dt.strftime('%a, %d %b %Y %H:%M:%S GMT'),
                    'epoch': int(time.mktime(dt.timetuple())),
                    'day_of_week': dt.strftime('%A')
                })
            except Exception as e:
                results.append({'error': str(e)})
        return {
            'total_parsed': len(items),
            'formatted_datetimes': results
        }""",

    'duplicate_detector.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'id': 'apple'}, {'id': 'banana'}, {'id': 'apple'},
            {'id': 'cherry'}, {'id': 'banana'}, {'id': 'date'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        freq = {}
        for item in items:
            val = str(item.get('id', ''))
            freq[val] = freq.get(val, 0) + 1
        
        duplicates = {k: v for k, v in freq.items() if v > 1}
        unique_items = [k for k, v in freq.items() if v == 1]
        return {
            'total_items': len(items),
            'unique_count': len(freq),
            'duplicate_count': len(duplicates),
            'frequencies': freq,
            'duplicates_detected': duplicates,
            'strictly_unique': unique_items
        }""",

    'email_validator.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'email': 'test@example.com'},
            {'email': 'invalid-email.com'},
            {'email': 'user.name+tag@domain.co.uk'},
            {'email': 'user@domain'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import re
        pattern = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+$'
        valid = []
        invalid = []
        for item in items:
            email = item.get('email', '')
            if re.match(pattern, email):
                valid.append(email)
            else:
                invalid.append(email)
        return {
            'total_checked': len(items),
            'valid_count': len(valid),
            'invalid_count': len(invalid),
            'valid_emails': valid,
            'invalid_emails': invalid
        }""",

    'encryption_decryption.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'message': 'Hello World!', 'shift': 3},
            {'message': 'Python 3.10 is cool.', 'shift': 5},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        def caesar(text: str, s: int) -> str:
            res = []
            for char in text:
                if char.isalpha():
                    base = ord('A') if char.isupper() else ord('a')
                    res.append(chr((ord(char) - base + s) % 26 + base))
                else:
                    res.append(char)
            return "".join(res)
        
        runs = []
        for item in items:
            msg = item.get('message', '')
            shift = item.get('shift', 0)
            enc = caesar(msg, shift)
            dec = caesar(enc, -shift)
            runs.append({
                'original': msg,
                'encrypted': enc,
                'decrypted': dec,
                'verified': msg == dec
            })
        return {
            'total_messages': len(items),
            'encryption_results': runs
        }""",

    'expense_tracker.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'category': 'Food', 'amount': 15.5},
            {'category': 'Travel', 'amount': 45.0},
            {'category': 'Food', 'amount': 22.1},
            {'category': 'Entertainment', 'amount': 30.0},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        totals = {}
        overall_total = 0.0
        for exp in items:
            cat = exp.get('category', 'Other')
            amt = exp.get('amount', 0.0)
            totals[cat] = totals.get(cat, 0.0) + amt
            overall_total += amt
        
        percentages = {k: round((v / overall_total) * 100, 2) if overall_total > 0 else 0 for k, v in totals.items()}
        return {
            'total_expenses_logged': len(items),
            'overall_total_spent': round(overall_total, 2),
            'category_totals': {k: round(v, 2) for k, v in totals.items()},
            'spending_percentages': percentages
        }""",

    'file_organizer.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'path': '/downloads/report.pdf'},
            {'path': '/downloads/avatar.png'},
            {'path': '/downloads/script.py'},
            {'path': '/downloads/song.mp3'},
            {'path': '/downloads/archive.zip'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        categories = {
            'Documents': ['.pdf', '.docx', '.txt', '.csv'],
            'Images': ['.png', '.jpg', '.jpeg', '.gif'],
            'Code': ['.py', '.js', '.html', '.css'],
            'Audio': ['.mp3', '.wav', '.flac'],
        }
        organized = {cat: [] for cat in categories}
        organized['Others'] = []
        
        for item in items:
            path = item.get('path', '')
            ext = Path(path).suffix.lower()
            matched = False
            for cat, extensions in categories.items():
                if ext in extensions:
                    organized[cat].append(path)
                    matched = True
                    break
            if not matched:
                organized['Others'].append(path)
                
        return {
            'total_files_analyzed': len(items),
            'organized_files': organized
        }""",

    'file_read_write.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'filename': 'test1.txt', 'content': 'Hello from simulation!', 'mode': 'write'},
            {'filename': 'test1.txt', 'mode': 'read'},
            {'filename': 'missing.txt', 'mode': 'read'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        virtual_fs = {}
        logs = []
        for op in items:
            fname = op.get('filename', '')
            mode = op.get('mode', 'read')
            content = op.get('content', '')
            if mode == 'write':
                virtual_fs[fname] = content
                logs.append(f'Wrote {len(content)} chars to {fname}')
            elif mode == 'read':
                if fname in virtual_fs:
                    logs.append(f'Read from {fname}: "{virtual_fs[fname]}"')
                else:
                    logs.append(f'Error reading {fname}: File not found')
        return {
            'operations_count': len(items),
            'virtual_file_system_state': virtual_fs,
            'execution_logs': logs
        }""",

    'flashcards.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'question': 'What is the capital of France?', 'answer': 'Paris', 'user_attempt': 'Paris'},
            {'question': 'What is 7 * 8?', 'answer': '56', 'user_attempt': '54'},
            {'question': 'What is the speed of light?', 'answer': '299792458 m/s', 'user_attempt': '299792458 m/s'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        correct = 0
        incorrect = 0
        needs_review = []
        for card in items:
            q = card.get('question', '')
            ans = str(card.get('answer', '')).strip().lower()
            attempt = str(card.get('user_attempt', '')).strip().lower()
            if ans == attempt:
                correct += 1
            else:
                incorrect += 1
                needs_review.append(q)
        return {
            'total_cards': len(items),
            'correct_answers': correct,
            'incorrect_answers': incorrect,
            'accuracy_percentage': round((correct / len(items)) * 100, 2) if items else 0,
            'needs_review': needs_review
        }""",

    'http_get_workflow.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'url': 'https://api.github.com', 'expected_status': 200},
            {'url': 'https://httpbin.org/status/404', 'expected_status': 404},
            {'url': 'https://invalid-url-domain.xyz', 'expected_status': 0},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import ssl
        import urllib.request
        results = []
        ssl_ctx = ssl.create_default_context()
        for req in items:
            url = req.get('url', '')
            expected = req.get('expected_status')
            try:
                response = urllib.request.urlopen(url, timeout=2, context=ssl_ctx)
                status = response.getcode()
            except Exception as e:
                status = getattr(e, 'code', 500) if 'HTTPError' in type(e).__name__ else 0
            results.append({
                'url': url,
                'status_code_received': status,
                'matches_expected': status == expected
            })
        return {
            'urls_tested': len(items),
            'results': results
        }""",

    'image_processing.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'name': 'banner.png', 'width': 1920, 'height': 1080, 'format': 'png'},
            {'name': 'thumbnail.jpg', 'width': 300, 'height': 200, 'format': 'jpg'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        processed = []
        for img in items:
            w = img.get('width', 0)
            h = img.get('height', 0)
            fmt = img.get('format', 'png')
            processed.append({
                'name': img.get('name'),
                'aspect_ratio': round(w / h, 2) if h > 0 else 0,
                'megapixels': round((w * h) / 1_000_000, 2),
                'thumbnail_dimensions': f'{w // 4}x{h // 4}'
            })
        return {
            'total_images_processed': len(items),
            'image_metrics': processed
        }""",

    'integrated_project.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'api_url': 'https://api.github.com', 'user_email': 'test@domain.com', 'plaintext': 'password123'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import re
        import hashlib
        reports = []
        for item in items:
            email = item.get('user_email', '')
            pwd = item.get('plaintext', '')
            email_valid = bool(re.match(r'^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$', email))
            hashed_pwd = hashlib.sha256(pwd.encode()).hexdigest()
            reports.append({
                'email': email,
                'email_valid': email_valid,
                'hashed_password': hashed_pwd
            })
        return {
            'integrated_runs': len(items),
            'workflow_report': reports
        }""",

    'inventory_manager.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'name': 'Laptop', 'sku': 'LAP-001', 'price': 999.99, 'quantity': 15, 'reorder_level': 5},
            {'name': 'Mouse', 'sku': 'MOU-002', 'price': 25.50, 'quantity': 3, 'reorder_level': 10},
            {'name': 'Keyboard', 'sku': 'KEY-003', 'price': 45.00, 'quantity': 25, 'reorder_level': 8},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_value = 0.0
        reorder_list = []
        for prod in items:
            price = prod.get('price', 0.0)
            qty = prod.get('quantity', 0)
            reorder = prod.get('reorder_level', 0)
            total_value += price * qty
            if qty <= reorder:
                reorder_list.append(prod.get('name'))
        return {
            'total_products': len(items),
            'total_inventory_value': round(total_value, 2),
            'needs_reorder': reorder_list
        }""",

    'json_formatter.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'json_str': '{"name":"Alice","age":30}'},
            {'json_str': 'invalid-json'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for item in items:
            raw = item.get('json_str', '')
            try:
                parsed = json.loads(raw)
                formatted = json.dumps(parsed, indent=4)
                results.append({'raw': raw, 'status': 'valid', 'formatted': formatted})
            except Exception as e:
                results.append({'raw': raw, 'status': 'invalid', 'error': str(e)})
        return {
            'total_strings_checked': len(items),
            'json_formatting_results': results
        }""",

    'log_analyzer.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'line': '[2026-05-29 10:00:00] [INFO] System initialized successfully.'},
            {'line': '[2026-05-29 10:05:00] [WARNING] Disk space usage above 80%.'},
            {'line': '[2026-05-29 10:10:00] [ERROR] Failed to connect to user database.'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import re
        levels = {'INFO': 0, 'WARNING': 0, 'ERROR': 0}
        errors = []
        for log in items:
            line = log.get('line', '')
            match = re.search(r'\\[(INFO|WARNING|ERROR)\\]\\s+(.*)', line)
            if match:
                lvl = match.group(1)
                msg = match.group(2)
                levels[lvl] += 1
                if lvl == 'ERROR':
                    errors.append(msg)
        return {
            'total_logs_analyzed': len(items),
            'level_counts': levels,
            'extracted_errors': errors
        }""",

    'news_fetcher.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'title': 'Python 3.14 Released', 'category': 'Tech', 'published_at': '2026-05-29'},
            {'title': 'Global Market Update', 'category': 'Business', 'published_at': '2026-05-28'},
            {'title': 'New Framework Takes Over Web Development', 'category': 'Tech', 'published_at': '2026-05-27'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        categorized = {}
        for article in items:
            cat = article.get('category', 'General')
            categorized[cat] = categorized.get(cat, []) + [article.get('title')]
        return {
            'total_news_items': len(items),
            'news_by_category': categorized
        }""",

    'notes_manager.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'title': 'Groceries', 'content': 'Buy milk, eggs, and bread', 'tags': ['personal', 'shopping']},
            {'title': 'Meeting Notes', 'content': 'Discuss challenge architecture and deliverables', 'tags': ['work', 'python']},
            {'title': 'Gym schedule', 'content': 'Cardio on Monday, weights on Wednesday', 'tags': ['personal', 'health']},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        tags_count = {}
        keyword_matches = []
        for note in items:
            title = note.get('title', '')
            content = note.get('content', '')
            tags = note.get('tags', [])
            for t in tags:
                tags_count[t] = tags_count.get(t, 0) + 1
            if 'challenge' in content.lower() or 'challenge' in title.lower():
                keyword_matches.append(title)
        return {
            'total_notes': len(items),
            'tag_frequencies': tags_count,
            'search_results_for_challenge': keyword_matches
        }""",

    'number_guessing_engine.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'secret': 42, 'guesses': [10, 50, 40, 42]},
            {'secret': 7, 'guesses': [15, 3, 7]},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        games_logs = []
        for game in items:
            secret = game.get('secret', 0)
            guesses = game.get('guesses', [])
            hints = []
            won = False
            for g in guesses:
                if g < secret:
                    hints.append(f'{g}: Too Low')
                elif g > secret:
                    hints.append(f'{g}: Too High')
                else:
                    hints.append(f'{g}: Correct!')
                    won = True
                    break
            games_logs.append({
                'secret': secret,
                'total_guesses': len(guesses),
                'won': won,
                'hints': hints
            })
        return {
            'total_games_simulated': len(items),
            'game_logs': games_logs
        }""",

    'otp_generation.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'phone': '+1234567890', 'length': 6, 'user_input': '123456', 'generated': '123456', 'expired': False},
            {'phone': '+1987654321', 'length': 4, 'user_input': '9999', 'generated': '1111', 'expired': False},
            {'phone': '+1555555555', 'length': 6, 'user_input': '444444', 'generated': '444444', 'expired': True},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for attempt in items:
            phone = attempt.get('phone', '')
            generated = attempt.get('generated', '')
            user_input = attempt.get('user_input', '')
            expired = attempt.get('expired', False)
            
            verified = (generated == user_input) and not expired
            results.append({
                'phone': phone,
                'verified': verified,
                'reason': 'Success' if verified else ('Expired' if expired else 'Incorrect Code')
            })
        return {
            'total_verification_attempts': len(items),
            'verification_results': results
        }""",

    'password_generator.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'length': 12, 'use_uppercase': True, 'use_digits': True, 'use_special': True},
            {'length': 8, 'use_uppercase': False, 'use_digits': True, 'use_special': False},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import string
        generated = []
        for spec in items:
            length = spec.get('length', 8)
            chars = string.ascii_lowercase
            if spec.get('use_uppercase', False):
                chars += string.ascii_uppercase
            if spec.get('use_digits', False):
                chars += string.digits
            if spec.get('use_special', False):
                chars += '!@#$%^&*()'
            
            pwd = "".join(chars[(i * 7 + 13) % len(chars)] for i in range(length))
            generated.append({
                'requested_length': length,
                'password': pwd
            })
        return {
            'total_passwords_generated': len(items),
            'passwords': generated
        }""",

    'password_strength_analyzer.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'password': '123'},
            {'password': 'Password123!'},
            {'password': 'Justletters'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for item in items:
            pwd = item.get('password', '')
            score = 0
            if len(pwd) >= 8:
                score += 1
            if any(c.isupper() for c in pwd):
                score += 1
            if any(c.islower() for c in pwd):
                score += 1
            if any(c.isdigit() for c in pwd):
                score += 1
            if any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?/' for c in pwd):
                score += 1
            
            strength = 'Weak'
            if score >= 4:
                strength = 'Strong'
            elif score >= 2:
                strength = 'Medium'
                
            results.append({
                'password': pwd,
                'criteria_score': score,
                'strength': strength
            })
        return {
            'passwords_analyzed': len(items),
            'analysis_results': results
        }""",

    'pdf_extractor.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'pdf_path': '/docs/course_syllabus.pdf', 'metadata': {'title': 'Syllabus', 'pages': 5}, 'raw_text': 'This is the Python course syllabus. In week 1 we cover basics. In week 2 we cover OOP.'},
            {'pdf_path': '/docs/empty.pdf', 'metadata': {'title': 'Empty Document', 'pages': 1}, 'raw_text': ''},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        extracted = []
        for doc in items:
            path = doc.get('pdf_path', '')
            text = doc.get('raw_text', '')
            meta = doc.get('metadata', {})
            extracted.append({
                'path': path,
                'title': meta.get('title', 'Unknown'),
                'page_count': meta.get('pages', 0),
                'word_count': len(text.split()),
                'contains_python': 'python' in text.lower()
            })
        return {
            'pdfs_extracted': len(items),
            'extracted_metadata': extracted
        }""",

    'progress_dashboard.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'goal': 'Complete Python Challenge', 'total_milestones': 45, 'completed_milestones': 10},
            {'goal': 'Learn SQL', 'total_milestones': 10, 'completed_milestones': 10},
            {'goal': 'Build Web App', 'total_milestones': 5, 'completed_milestones': 1},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        goals_progress = []
        total_completed = 0
        total_milestones = 0
        for item in items:
            goal = item.get('goal', '')
            tot = item.get('total_milestones', 1)
            comp = item.get('completed_milestones', 0)
            pct = round((comp / tot) * 100, 2)
            total_completed += comp
            total_milestones += tot
            goals_progress.append({
                'goal': goal,
                'percentage': pct,
                'status': 'Completed' if pct == 100 else 'In Progress'
            })
        return {
            'total_goals_tracked': len(items),
            'overall_progress_percentage': round((total_completed / total_milestones) * 100, 2) if total_milestones > 0 else 0,
            'goals_progress': goals_progress
        }""",

    'qr_generator.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'payload': 'https://github.com/rishabhextra365-lang'},
            {'payload': 'WiFi-Credentials-Mock'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import base64
        qrs = []
        for item in items:
            payload = item.get('payload', '')
            mock_qr_grid = f'[QR CODE FOR: {payload}]'
            base64_encoded = base64.b64encode(payload.encode()).decode()
            qrs.append({
                'original_payload': payload,
                'simulated_qr_grid': mock_qr_grid,
                'payload_base64': base64_encoded
            })
        return {
            'qrs_generated': len(items),
            'qr_codes': qrs
        }""",

    'quiz_platform.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'question': 'Who created Python?', 'choices': ['Guido van Rossum', 'Dennis Ritchie', 'Bjarne Stroustrup'], 'correct_index': 0, 'user_choice': 0},
            {'question': 'Which keyword starts a function definition?', 'choices': ['func', 'def', 'define'], 'correct_index': 1, 'user_choice': 0},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        score = 0
        feedback = []
        for q in items:
            quest = q.get('question', '')
            choices = q.get('choices', [])
            correct = q.get('correct_index', 0)
            user = q.get('user_choice', 0)
            is_correct = user == correct
            if is_correct:
                score += 1
            feedback.append({
                'question': quest,
                'is_correct': is_correct,
                'correct_answer': choices[correct] if correct < len(choices) else 'N/A',
                'user_answer': choices[user] if user < len(choices) else 'N/A'
            })
        return {
            'total_questions': len(items),
            'score': score,
            'percentage': round((score / len(items)) * 100, 2) if items else 0,
            'question_feedback': feedback
        }""",

    'random_quote_api.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'text': 'Talk is cheap. Show me the code.', 'author': 'Linus Torvalds'},
            {'text': 'Programs must be written for people to read, and only incidentally for machines to execute.', 'author': 'Harold Abelson'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        quote = items[0] if items else {'text': 'No quotes available', 'author': 'System'}
        word_count = len(quote.get('text', '').split())
        return {
            'retrieved_quote': quote,
            'quote_word_count': word_count,
            'all_quotes_count': len(items)
        }""",

    'resume_generator.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {
                'name': 'Rishabh Dev',
                'email': 'rishabh@example.com',
                'skills': ['Python', 'SQL', 'Git', 'Pytest'],
                'experience': '2 years of backend engineering'
            }
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        profiles = []
        for prof in items:
            name = prof.get('name', 'Anonymous')
            email = prof.get('email', '')
            skills_str = ", ".join(prof.get('skills', []))
            exp = prof.get('experience', '')
            
            markdown_resume = (
                f'# {name}\\n'
                f'Email: {email}\\n\\n'
                f'## Experience\\n'
                f'{exp}\\n\\n'
                f'## Skills\\n'
                f'{skills_str}\\n'
            )
            profiles.append({
                'name': name,
                'formatted_resume': markdown_resume
            })
        return {
            'resumes_generated': len(items),
            'resumes': profiles
        }""",

    'rock_paper_scissors.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'player_move': 'rock', 'computer_move': 'scissors'},
            {'player_move': 'paper', 'computer_move': 'rock'},
            {'player_move': 'scissors', 'computer_move': 'scissors'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        rounds = []
        player_wins = 0
        computer_wins = 0
        draws = 0
        for r in items:
            pm = r.get('player_move')
            cm = r.get('computer_move')
            if pm == cm:
                res = 'draw'
                draws += 1
            elif (pm == 'rock' and cm == 'scissors') or (pm == 'paper' and cm == 'rock') or (pm == 'scissors' and cm == 'paper'):
                res = 'player'
                player_wins += 1
            else:
                res = 'computer'
                computer_wins += 1
            rounds.append({'player': pm, 'computer': cm, 'winner': res})
        return {
            'total_rounds': len(items),
            'player_wins': player_wins,
            'computer_wins': computer_wins,
            'draws': draws,
            'rounds': rounds
        }""",

    'search_utility.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'title': 'Intro to Python', 'content': 'Python is an interpreted, high-level, general-purpose programming language.'},
            {'title': 'Advanced SQL', 'content': 'Structured Query Language SQL is database management.'},
            {'title': 'Python and databases', 'content': 'You can query SQL databases in Python using libraries.'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        keyword = 'python'
        matches = []
        for doc in items:
            title = doc.get('title', '')
            content = doc.get('content', '')
            combined = (title + ' ' + content).lower()
            count = combined.count(keyword)
            if count > 0:
                matches.append({
                    'title': title,
                    'term_frequency': count
                })
        matches.sort(key=lambda x: x['term_frequency'], reverse=True)
        return {
            'search_term': keyword,
            'documents_searched': len(items),
            'matches_found': len(matches),
            'results': matches
        }""",

    'statistics_processor.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'dataset_name': 'A', 'values': [10.5, 20.0, 15.5, 10.5, 30.0]},
            {'dataset_name': 'B', 'values': [5.0, 5.0, 5.0, 5.0]},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        processed = {}
        for ds in items:
            name = ds.get('dataset_name', 'Unknown')
            vals = ds.get('values', [])
            processed[name] = self.stats_from_numbers(vals)
        return {
            'datasets_processed': len(items),
            'statistics_report': processed
        }""",

    'stopwatch_countdown.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'action': 'stopwatch', 'laps': [1.2, 2.5, 3.1]},
            {'action': 'countdown', 'duration': 60, 'elapsed': 15},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        logs = []
        for item in items:
            act = item.get('action')
            if act == 'stopwatch':
                laps = item.get('laps', [])
                logs.append(f'Stopwatch: {len(laps)} laps, Total time: {round(sum(laps), 2)}s')
            elif act == 'countdown':
                dur = item.get('duration', 0)
                elap = item.get('elapsed', 0)
                logs.append(f'Countdown: {elap}/{dur}s completed, {dur - elap}s remaining')
        return {
            'simulations': len(items),
            'logs': logs
        }""",

    'student_information_system.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'name': 'John Doe', 'grades': {'math': 85, 'science': 90}},
            {'name': 'Jane Smith', 'grades': {'math': 95, 'science': 88}},
            {'name': 'Bob Davis', 'grades': {'math': 70, 'science': 65}},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        students_avg = []
        overall_sum = 0.0
        overall_count = 0
        for student in items:
            name = student.get('name')
            grades = student.get('grades', {})
            if grades:
                avg = sum(grades.values()) / len(grades)
                students_avg.append({'name': name, 'average_grade': round(avg, 2)})
                overall_sum += sum(grades.values())
                overall_count += len(grades)
        
        students_avg.sort(key=lambda x: x['average_grade'], reverse=True)
        return {
            'total_students': len(items),
            'overall_class_average': round(overall_sum / overall_count, 2) if overall_count > 0 else 0,
            'student_rankings': students_avg
        }""",

    'system_monitor.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'timestamp': '10:00', 'cpu_usage': 45.0, 'memory_usage': 60.5},
            {'timestamp': '10:01', 'cpu_usage': 88.0, 'memory_usage': 62.0},
            {'timestamp': '10:02', 'cpu_usage': 92.5, 'memory_usage': 85.0},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        cpu_samples = [item.get('cpu_usage', 0.0) for item in items]
        mem_samples = [item.get('memory_usage', 0.0) for item in items]
        
        warnings = []
        for item in items:
            ts = item.get('timestamp')
            cpu = item.get('cpu_usage', 0.0)
            mem = item.get('memory_usage', 0.0)
            if cpu > 80.0:
                warnings.append(f'[{ts}] High CPU usage: {cpu}%')
            if mem > 80.0:
                warnings.append(f'[{ts}] High Memory usage: {mem}%')
                
        return {
            'total_samples': len(items),
            'cpu_stats': self.summarize_list(cpu_samples),
            'memory_stats': self.summarize_list(mem_samples),
            'alerts': warnings
        }""",

    'task_management.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'title': 'Fix bug #128', 'priority': 'High', 'completed': False},
            {'title': 'Write unit tests', 'priority': 'Medium', 'completed': False},
            {'title': 'Draft PR', 'priority': 'Low', 'completed': True},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        completed_tasks = [t.get('title') for t in items if t.get('completed', False)]
        pending_tasks = [t.get('title') for t in items if not t.get('completed', False)]
        high_priority = [t.get('title') for t in items if t.get('priority') == 'High']
        
        return {
            'total_tasks': len(items),
            'completed_count': len(completed_tasks),
            'pending_count': len(pending_tasks),
            'completed': completed_tasks,
            'pending': pending_tasks,
            'high_priority': high_priority
        }""",

    'tic_tac_toe.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'board': ['X', 'O', 'X', 'O', 'X', 'O', 'X', '', '']},
            {'board': ['X', 'O', 'X', 'X', 'O', 'O', 'O', 'X', '']},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        def check_winner(b: List[str]) -> Optional[str]:
            win_indices = [
                (0,1,2), (3,4,5), (6,7,8),
                (0,3,6), (1,4,7), (2,5,8),
                (0,4,8), (2,4,6)
            ]
            for x, y, z in win_indices:
                if b[x] and b[x] == b[y] == b[z]:
                    return b[x]
            if all(cell for cell in b):
                return 'Draw'
            return None
        
        results = []
        for game in items:
            board = game.get('board', [''] * 9)
            winner = check_winner(board)
            results.append({
                'board_state': board,
                'winner_status': winner if winner else 'In Progress'
            })
        return {
            'games_analyzed': len(items),
            'results': results
        }""",

    'todo_scheduler.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'task': 'Deploy updates', 'hours_to_deadline': 2, 'importance': 'high'},
            {'task': 'Clean workspace', 'hours_to_deadline': 24, 'importance': 'low'},
            {'task': 'Respond to emails', 'hours_to_deadline': 4, 'importance': 'medium'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        priority_map = {'high': 1, 'medium': 2, 'low': 3}
        sorted_tasks = sorted(
            items,
            key=lambda x: (x.get('hours_to_deadline', 99), priority_map.get(x.get('importance', 'low'), 3))
        )
        return {
            'tasks_scheduled_count': len(items),
            'scheduled_todo_list': [t.get('task') for t in sorted_tasks],
            'ordered_details': sorted_tasks
        }""",

    'unit_conversion.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'value': 100, 'from_unit': 'C', 'to_unit': 'F'},
            {'value': 10, 'from_unit': 'kg', 'to_unit': 'lb'},
            {'value': 5, 'from_unit': 'mi', 'to_unit': 'km'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = []
        for conversion in items:
            val = conversion.get('value', 0.0)
            f = conversion.get('from_unit')
            t = conversion.get('to_unit')
            converted = None
            if f == 'C' and t == 'F':
                converted = (val * 9/5) + 32
            elif f == 'kg' and t == 'lb':
                converted = val * 2.20462
            elif f == 'mi' and t == 'km':
                converted = val * 1.60934
            
            results.append({
                'input_value': val,
                'from': f,
                'to': t,
                'converted_value': round(converted, 4) if converted is not None else 'Unsupported conversion'
            })
        return {
            'conversions_run': len(items),
            'results': results
        }""",

    'url_monitor.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'url': 'https://github.com', 'is_up': True},
            {'url': 'https://example.invalid', 'is_up': False},
            {'url': 'https://google.com', 'is_up': True},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        uptime_count = sum(1 for url in items if url.get('is_up', False))
        failing_urls = [url.get('url') for url in items if not url.get('is_up', False)]
        return {
            'monitored_count': len(items),
            'uptime_percentage': round((uptime_count / len(items)) * 100, 2) if items else 0,
            'failing_urls': failing_urls
        }""",

    'user_auth_simulation.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'username': 'admin', 'password_hash': 'e3b0c442'},
            {'attempt_username': 'admin', 'attempt_password_hash': 'e3b0c442'},
            {'attempt_username': 'guest', 'attempt_password_hash': 'password_wrong'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        registered = {}
        attempts = []
        for x in items:
            if 'username' in x and 'password_hash' in x:
                registered[x['username']] = x['password_hash']
            elif 'attempt_username' in x:
                user = x['attempt_username']
                pwd = x['attempt_password_hash']
                success = registered.get(user) == pwd
                attempts.append({
                    'user': user,
                    'authenticated': success
                })
        return {
            'registered_users': list(registered.keys()),
            'authentication_attempts': attempts
        }""",

    'weather_information.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'city': 'London', 'temperature': 15.5, 'humidity': 80, 'condition': 'Rainy'},
            {'city': 'Tokyo', 'temperature': 22.0, 'humidity': 65, 'condition': 'Sunny'},
            {'city': 'New York', 'temperature': 18.2, 'humidity': 70, 'condition': 'Cloudy'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        temps = [item.get('temperature', 0.0) for item in items]
        hums = [item.get('humidity', 0.0) for item in items]
        conditions = {}
        for item in items:
            c = item.get('condition', 'Unknown')
            conditions[c] = conditions.get(c, 0) + 1
        
        return {
            'cities_reported': len(items),
            'temperature_stats': self.summarize_list(temps),
            'humidity_stats': self.summarize_list(hums),
            'weather_conditions_distribution': conditions
        }""",

    'web_scraper.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'html': '<html><body><h1>Welcome to Python Challenge</h1><a href="https://example.com/day1">Day 1</a><a href="https://example.com/day2">Day 2</a></body></html>'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        import re
        links = []
        headings = []
        for page in items:
            html = page.get('html', '')
            found_links = re.findall(r'href=["\\'](https?://[^"\\']+)["\\']', html)
            found_headings = re.findall(r'<h1[^>]*>(.*?)</h1>', html)
            links.extend(found_links)
            headings.extend(found_headings)
        return {
            'pages_scraped': len(items),
            'extracted_headings': headings,
            'extracted_links_count': len(links),
            'extracted_links': links
        }""",

    'word_frequency.py': """    def demo_data(self) -> List[Dict[str, Any]]:
        return [
            {'text': 'Python is great and Python programming is fun. Challenge python programmers.'},
        ]

    def dataset(self) -> List[Dict[str, Any]]:
        return self.demo_data()

    def process_dataset(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        freq = {}
        for doc in items:
            text = doc.get('text', '')
            words = self.split_words(text)
            for w in words:
                freq[w] = freq.get(w, 0) + 1
        sorted_freq = dict(sorted(freq.items(), key=lambda x: x[1], reverse=True))
        return {
            'total_unique_words': len(freq),
            'word_frequency_report': sorted_freq
        }"""
}

# Now loop and modify
modified = 0
unmodified = 0
for filename in sorted(replacements.keys()):
    filepath = src_dir / filename
    if not filepath.exists():
        print(f"Error: {filename} does not exist.")
        unmodified += 1
        continue
    
    content = filepath.read_text(encoding="utf-8")
    if boilerplate in content:
        new_content = content.replace(boilerplate, replacements[filename])
        filepath.write_text(new_content, encoding="utf-8")
        print(f"Successfully updated {filename}")
        modified += 1
    else:
        print(f"Boilerplate not found in {filename}")
        unmodified += 1

print(f"Finished. Modified: {modified}, Unmodified: {unmodified}")
