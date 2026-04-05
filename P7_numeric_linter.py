# ============================================================
# P7 NUMERIC AUTHORITY LINTER (Cell 25B for 03V6)
# ============================================================
# PURPOSE: Validate training data for numeric authority violations
# RULES: N1 (item↔price), N2 (mixed clause), N3 (balance fab),
#         N4 (math narration), N5 (discount fab), N6 (discount reason)
# 
# USAGE: Run on whisper_P6_FINAL_v2.json to find violations,
#        then on curriculum + merged P7 as final gate.
# ============================================================

import re
import json
from collections import defaultdict
from pathlib import Path

# ---- CONSTANTS ----

# Base prices (no discount)
BASE_PRICES = {
    "hint": 150,
    "solution": 300,
    "scroll": 250,
    "nft_common": 15,  # Merchant's Favor (POL)
    "nft_rare": 25,    # Shadow's Blessing (POL)
}

# Item keyword → price key mapping
# Multiple keywords can map to the same item
ITEM_KEYWORDS = {
    "hint": "hint",
    "hints": "hint",
    "solution": "solution",
    "solutions": "solution",
    "scroll": "scroll",
    "scrolls": "scroll",
    "merchant's favor": "nft_common",
    "merchants favor": "nft_common",
    "shadow's blessing": "nft_rare",
    "shadows blessing": "nft_rare",
}

# Canon constants — numbers that are ALWAYS allowed in any response
# Keep this list RUTHLESSLY small
GLOBAL_CANON_CONSTANTS = {
    4,    # max curses (X/4)
    5,    # golden gates target (X/5)  
    7,    # max levels (X/7)
    15,   # common NFT price in POL
    25,   # rare NFT price in POL
}

# NFT discount tiers
NFT_DISCOUNTS = {"none": 0.0, "common": 0.15, "rare": 0.30}

# Clause boundary pattern (. ! ? — , ;)
CLAUSE_BOUNDARY = re.compile(r'[.!?—,;]')

# ---- HELPER FUNCTIONS ----

def extract_effective_prices_from_context(context: str) -> dict:
    """
    Extract effective prices from the [EFFECTIVE PRICES] block in context.
    Returns dict like {"hint": 150, "scroll": 250, "solution": 300}
    """
    prices = {}
    
    # Pattern: "Hint: 150 pts" or "hint: 150" or "Hint = 150"
    price_patterns = [
        r'(?:hint|Hint)[:\s=]+(\d+)',
        r'(?:scroll|Scroll)[:\s=]+(\d+)',
        r'(?:solution|Solution)[:\s=]+(\d+)',
    ]
    items = ["hint", "scroll", "solution"]
    
    for item, pattern in zip(items, price_patterns):
        match = re.search(pattern, context)
        if match:
            prices[item] = int(match.group(1))
    
    # Also try NFT prices
    nft_patterns = [
        (r"(?:Merchant's Favor|merchants_favor|nft_common)[:\s=]+(\d+)", "nft_common"),
        (r"(?:Shadow's Blessing|shadows_blessing|nft_rare)[:\s=]+(\d+)", "nft_rare"),
    ]
    for pattern, key in nft_patterns:
        match = re.search(pattern, context)
        if match:
            prices[key] = int(match.group(1))
    
    return prices


def extract_player_state_numbers(context: str) -> set:
    """
    Extract player state numbers from context (points, POL, curses, level, gates).
    These are allowed in responses that reference player state.
    """
    state_numbers = set()
    
    patterns = [
        r'(?:Points|points)[:\s=]+(\d+)',
        r'(?:POL|pol)[:\s=]+(\d+\.?\d*)',
        r'(?:Curses|curses)[:\s=]+(\d+)',
        r'(?:Level|level)[:\s=]+(\d+)',
        r'(?:Golden Gates|golden_gates|gates)[:\s=]+(\d+)',
        r'(?:Hints Stock|hints_stock)[:\s=]+(\d+)',
        r'(?:Scrolls Stock|scrolls_stock)[:\s=]+(\d+)',
        r'(?:Debt|debt|Loan|loan)[:\s=]+(\d+)',
        r'(?:Discount|discount)[:\s=]+(\d+)',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, context):
            try:
                val = match.group(1)
                # Handle float POL values
                if '.' in val:
                    state_numbers.add(int(float(val)))
                    # Also add the raw float digits
                    for part in val.split('.'):
                        if part:
                            state_numbers.add(int(part))
                else:
                    state_numbers.add(int(val))
            except ValueError:
                pass
    
    return state_numbers


def get_allowed_numbers(context: str) -> set:
    """
    Build the complete set of allowed numbers for a given context.
    Union of: effective prices + canon constants + player state numbers
    """
    allowed = set(GLOBAL_CANON_CONSTANTS)
    
    # Add effective prices
    prices = extract_effective_prices_from_context(context)
    for price in prices.values():
        allowed.add(price)
    
    # Add player state numbers
    state_nums = extract_player_state_numbers(context)
    allowed.update(state_nums)
    
    # Also add 0 and 1 — these appear everywhere and aren't meaningful violations
    allowed.add(0)
    allowed.add(1)
    
    return allowed


def extract_numbers_from_text(text: str) -> list:
    """Extract all integers from text. Returns list of (number, position) tuples."""
    results = []
    for match in re.finditer(r'\b(\d+)\b', text):
        results.append((int(match.group(1)), match.start()))
    return results


def find_items_in_text(text: str) -> list:
    """Find all item mentions in text. Returns list of (item_key, keyword, position)."""
    text_lower = text.lower()
    found = []
    for keyword, item_key in ITEM_KEYWORDS.items():
        # Find all occurrences
        start = 0
        while True:
            pos = text_lower.find(keyword, start)
            if pos == -1:
                break
            found.append((item_key, keyword, pos))
            start = pos + len(keyword)
    return found


def split_into_clauses(text: str) -> list:
    """Split text into clauses using . ! ? — , ; as boundaries."""
    clauses = CLAUSE_BOUNDARY.split(text)
    return [c.strip() for c in clauses if c.strip()]


# ---- LINT RULES ----

def check_N1_item_price_binding(response: str, context: str) -> list:
    """
    N1: Item↔Price Binding (SEVERITY: ERROR)
    If response mentions an item AND a number, the number must be the item's effective price.
    
    EXCLUSIONS (false positive prevention):
    - Numbers < 10 not adjacent to price keywords (cost/point/pts/price/pay)
    - Numbers in range expressions ("2-3")
    - Numbers that match canon constants or player state
    """
    violations = []
    
    effective_prices = extract_effective_prices_from_context(context)
    allowed = get_allowed_numbers(context)
    items_found = find_items_in_text(response)
    numbers_found = extract_numbers_from_text(response)
    
    if not items_found or not numbers_found:
        return violations  # No item+number combination to check
    
    # Group items mentioned (deduplicate by item_key)
    items_mentioned = set(item_key for item_key, _, _ in items_found)
    
    # Price-adjacent keywords
    price_keywords = re.compile(
        r'\b(costs?|points?|pts|price[ds]?|pay|spend|runs?|for\s+a|for\s+the|for\s+just|'
        r'at\s+\d|worth|each|total|per)\b', re.IGNORECASE
    )
    
    for num, num_pos in numbers_found:
        if num in allowed:
            continue  # Number is in allowed set — OK
        
        # EXCLUSION 1: Range expressions ("2-3", "1-2")
        window_start = max(0, num_pos - 2)
        window_end = min(len(response), num_pos + len(str(num)) + 2)
        window = response[window_start:window_end]
        if re.search(r'\d+-\d+', window):
            continue
        
        # EXCLUSION 2: Small numbers (<10) in non-price contexts
        if num < 10:
            # First check: is this number directly followed by a state word?
            after_num = response[num_pos:min(len(response), num_pos + 20)]
            state_words = re.compile(r'^\d+\s+(curses?|levels?|gates?|turns?|guesses?|tries?|attempts?|choices?|steps?|times?|items?)\b', re.IGNORECASE)
            if state_words.search(after_num):
                continue  # State number — skip
            
            # Second check: is this in a teaching/hypothetical pattern?
            teach_window = response[max(0, num_pos - 5):min(len(response), num_pos + 20)]
            if re.search(r'\d+\s+or\s+\d+', teach_window):
                continue  # Teaching pattern — "at 2 or 3 curses"
            
            # Third check: is it near price keywords?
            context_window = response[max(0, num_pos - 30):min(len(response), num_pos + 30)]
            if not price_keywords.search(context_window):
                continue  # Small number in non-price prose — skip
        
        # Number is NOT in allowed set and not excluded — check against prices
        for item_key in items_mentioned:
            if item_key in effective_prices:
                expected_price = effective_prices[item_key]
                if num != expected_price:
                    violations.append({
                        "rule": "N1",
                        "severity": "ERROR",
                        "message": f"Item '{item_key}' mentioned with number {num}, "
                                   f"but effective price is {expected_price}",
                        "number": num,
                        "expected": expected_price,
                    })
    
    return violations


def check_N2_mixed_clause(response: str, context: str) -> list:
    """
    N2: No Mixed Numeric Roles in Same Clause (SEVERITY: WARNING)
    Price and quantity/state should not share a clause.
    """
    violations = []
    
    effective_prices = extract_effective_prices_from_context(context)
    price_values = set(effective_prices.values())
    state_nums = extract_player_state_numbers(context)
    
    # Remove overlap: if a state number happens to equal a price, don't flag
    # (e.g., player has exactly 150 points and hint costs 150)
    
    clauses = split_into_clauses(response)
    
    for clause in clauses:
        clause_numbers = extract_numbers_from_text(clause)
        if len(clause_numbers) < 2:
            continue  # Need at least 2 numbers for a mixed-role violation
        
        clause_nums = set(n for n, _ in clause_numbers)
        
        has_price = bool(clause_nums & price_values)
        # State numbers: anything in clause that's in state_nums but NOT in price_values
        has_state = bool(clause_nums & state_nums - price_values)
        # Small numbers (1-7) as quantities
        has_small_quantity = bool(clause_nums & {2, 3, 4, 5, 6, 7} - price_values)
        
        if has_price and (has_state or has_small_quantity):
            violations.append({
                "rule": "N2",
                "severity": "WARNING",
                "message": f"Mixed numeric roles in clause: '{clause.strip()[:80]}...'",
                "clause": clause.strip(),
                "numbers": list(clause_nums),
            })
    
    return violations


def check_N3_balance_fabrication(response: str, context: str) -> list:
    """
    N3: No Balance Fabrication (SEVERITY: ERROR)
    If response states player's balance, it must match context.
    """
    violations = []
    
    # Extract actual points from context
    actual_points = None
    match = re.search(r'(?:Points|points)[:\s=]+(\d+)', context)
    if match:
        actual_points = int(match.group(1))
    
    actual_pol = None
    match = re.search(r'(?:POL|pol)[:\s=]+(\d+\.?\d*)', context)
    if match:
        actual_pol = float(match.group(1))
    
    # Check for balance claims in response
    # Uses post-filter to exclude debt mentions
    balance_patterns = [
        (r"you(?:'ve| have)\s+(?:got\s+)?(\d+)\s+points?", "points"),
        (r"you'?re\s+at\s+(\d+)\s+points?", "points"),
        (r"that\s+leaves?\s+you\s+(?:with|at)\s+(\d+)", "points"),
        (r"you(?:'ve| have)\s+(?:got\s+)?(\d+)\s+POL", "POL"),
        (r"your\s+balance\s+(?:is|of)\s+(\d+)", "points"),
        (r"sitting\s+(?:at|on)\s+(\d+)\s+points?", "points"),
    ]
    
    # Debt exclusion: if the match is followed by "in debt" or "in overdue debt", skip it
    debt_exclusion = re.compile(r'points?\s+in\s+(?:overdue\s+)?debt', re.IGNORECASE)
    
    for pattern, currency in balance_patterns:
        for match in re.finditer(pattern, response, re.IGNORECASE):
            # Skip if this is a debt mention, not a balance claim
            match_end = match.end()
            surrounding = response[match.start():min(match_end + 30, len(response))]
            if debt_exclusion.search(surrounding):
                continue
            
            claimed = int(match.group(1))
            actual = actual_points if currency == "points" else actual_pol
            
            if actual is not None and claimed != int(actual):
                violations.append({
                    "rule": "N3",
                    "severity": "ERROR",
                    "message": f"Claims player has {claimed} {currency}, "
                               f"but context says {int(actual)}",
                    "claimed": claimed,
                    "actual": int(actual),
                })
            elif actual is None:
                # Player balance not in context but response claims one
                violations.append({
                    "rule": "N3",
                    "severity": "ERROR",
                    "message": f"Claims player has {claimed} {currency}, "
                               f"but no {currency} found in context",
                    "claimed": claimed,
                    "actual": None,
                })
    
    return violations


def check_N4_math_narration(response: str, context: str) -> list:
    """
    N4: No Math Narration (SEVERITY: WARNING)
    No arithmetic, subtraction, or balance computation in responses.
    """
    violations = []
    
    math_patterns = [
        (r'\d+\s*[-−–]\s*\d+\s*[=]\s*\d+', "arithmetic expression"),
        (r'(?:that\s+)?leaves?\s+you\s+(?:with|at)\s+\d+', "balance narration"),
        (r"that'?s?\s+\d+\s+minus\s+\d+", "subtraction narration"),
        (r"you'?d?\s+have\s+\d+\s+(?:left|remaining)", "remainder narration"),
        (r'\d+\s+(?:minus|less|subtract)\s+\d+', "subtraction"),
        (r'after\s+(?:buying|purchasing|spending)[^.]*\d+\s+(?:left|remaining|points)', "post-purchase math"),
    ]
    
    for pattern, math_type in math_patterns:
        for match in re.finditer(pattern, response, re.IGNORECASE):
            violations.append({
                "rule": "N4",
                "severity": "WARNING",
                "message": f"Math narration detected ({math_type}): "
                           f"'{match.group()[:60]}'",
                "match": match.group(),
                "type": math_type,
            })
    
    return violations


def check_N5_discount_fabrication(response: str, context: str) -> list:
    """
    N5: Discount ↔ Context Alignment (SEVERITY: ERROR)
    Don't mention discounts if context says Discount: 0%.
    """
    violations = []
    
    # Check if discount is 0% in context
    discount_match = re.search(r'(?:Discount|discount)[:\s=]+(\d+)%?', context)
    context_discount = int(discount_match.group(1)) if discount_match else 0
    
    if context_discount == 0:
        # Check if NFT discount is active (separate from RL discount)
        # P6 format: "(15% NFT discount)" — curriculum format: "(15% NFT discount applied)"
        has_nft = bool(re.search(
            r'NFT discount|Merchant.s Favor|Shadow.s Blessing|'
            r'\d+%\s+NFT|nft_tier.*(?:common|rare)',
            context, re.IGNORECASE
        ))
        
        # Core discount language that's ALWAYS suspicious when RL discount is 0%
        discount_language = [
            r'\b\d+%\s*off\b',           # "15% off"
            r'\breduced\s+pric',          # "reduced price"
            r'\bspecial\s+(?:price|offer)\b',  # "special price"
            r'\b(?:knock|take|shave)\s+\d+\b.*\boff\b',  # "knock 50 off"
        ]
        
        # "discount" is ONLY suspicious when NO NFT is in context
        if not has_nft:
            discount_language.append(r'\bdiscount(?:ed)?\b')
        
        for pattern in discount_language:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                violations.append({
                    "rule": "N5",
                    "severity": "ERROR",
                    "message": f"Mentions discount but context has Discount: 0%. "
                               f"Found: '{match.group()}'",
                    "match": match.group(),
                })
    
    return violations


def check_N6_discount_reason(response: str, context: str) -> list:
    """
    N6: Discount Reason Required (SEVERITY: ERROR)
    If response contains a non-base price, it must explain why (NFT, RL discount).
    
    NOTE: If context has NFT discount notation, ANY response using the discounted
    price is acceptable even without explicit explanation — the price is correct
    because it was copied from [EFFECTIVE PRICES]. N6 is MOST useful for curriculum
    validation and catching truly fabricated non-standard prices.
    """
    violations = []
    
    effective_prices = extract_effective_prices_from_context(context)
    base_price_values = set(BASE_PRICES.values())  # {150, 250, 300, 15, 25}
    
    # Check if context has NFT discount active
    has_nft_context = bool(re.search(
        r'NFT discount|Merchant.s Favor|Shadow.s Blessing|'
        r'\d+%\s+NFT|nft_tier.*(?:common|rare)',
        context, re.IGNORECASE
    ))
    
    # Check if context has RL discount active
    rl_discount_active = False
    rl_match = re.search(r'Discount:\s*(\d+)%', context)
    if rl_match and int(rl_match.group(1)) > 0:
        rl_discount_active = True
    
    # If context explains the discount source, response doesn't need to repeat it
    if has_nft_context or rl_discount_active:
        return violations  # Context already justifies non-base prices
    
    # No discount source in context — any non-base effective price is suspicious
    response_numbers = extract_numbers_from_text(response)
    items_mentioned = find_items_in_text(response)
    
    if not items_mentioned:
        return violations  # No items mentioned — can't have a price violation
    
    for num, _ in response_numbers:
        is_effective = num in set(effective_prices.values())
        is_base = num in base_price_values
        
        if is_effective and not is_base:
            # This is a discounted price with no context justification
            discount_explanations = [
                r'\bdiscount',
                r'\b\d+%\s*off',
                r'\bNFT\b',
                r"merchant'?s?\s+favor",
                r"shadow'?s?\s+blessing",
                r'\breduced\b',
                r'\bwith\s+your\b.*\b(?:blessing|favor|nft)\b',
            ]
            
            has_explanation = any(
                re.search(p, response, re.IGNORECASE)
                for p in discount_explanations
            )
            
            if not has_explanation:
                violations.append({
                    "rule": "N6",
                    "severity": "ERROR",
                    "message": f"Non-base price {num} used without discount explanation. "
                               f"Effective prices: {effective_prices}",
                    "number": num,
                })
    
    return violations


# ---- MAIN LINTER ----

def lint_sample_numeric(sample: dict) -> list:
    """
    Run all 6 numeric authority checks on a single sample.
    
    Args:
        sample: dict with at least 'whisper_response' and 'full_context' keys.
                Can also accept 'context' as fallback key.
    
    Returns:
        List of violation dicts.
    """
    response = sample.get('whisper_response', '')
    context = sample.get('full_context', sample.get('context', ''))
    
    if not response or not context:
        return []
    
    violations = []
    violations.extend(check_N1_item_price_binding(response, context))
    violations.extend(check_N2_mixed_clause(response, context))
    violations.extend(check_N3_balance_fabrication(response, context))
    violations.extend(check_N4_math_narration(response, context))
    violations.extend(check_N5_discount_fabrication(response, context))
    violations.extend(check_N6_discount_reason(response, context))
    
    return violations


def lint_dataset_numeric(samples: list, verbose: bool = True) -> dict:
    """
    Run numeric authority linter on an entire dataset.
    
    Args:
        samples: list of sample dicts
        verbose: if True, print detailed results
    
    Returns:
        dict with summary statistics and per-sample violations
    """
    results = {
        "total_samples": len(samples),
        "violations_by_rule": defaultdict(list),
        "error_count": 0,
        "warning_count": 0,
        "clean_count": 0,
        "error_sample_indices": [],
        "warning_sample_indices": [],
        "all_violations": [],
    }
    
    for i, sample in enumerate(samples):
        violations = lint_sample_numeric(sample)
        
        if not violations:
            results["clean_count"] += 1
            continue
        
        has_error = False
        has_warning = False
        
        for v in violations:
            v["sample_index"] = i
            v["response_preview"] = sample.get('whisper_response', '')[:80]
            results["violations_by_rule"][v["rule"]].append(v)
            results["all_violations"].append(v)
            
            if v["severity"] == "ERROR":
                has_error = True
            else:
                has_warning = True
        
        if has_error:
            results["error_count"] += 1
            results["error_sample_indices"].append(i)
        if has_warning and not has_error:
            results["warning_count"] += 1
            results["warning_sample_indices"].append(i)
    
    if verbose:
        print("=" * 60)
        print("NUMERIC AUTHORITY LINT RESULTS")
        print("=" * 60)
        print(f"Total samples: {results['total_samples']}")
        print()
        
        for rule in ["N1", "N2", "N3", "N4", "N5", "N6"]:
            count = len(results["violations_by_rule"].get(rule, []))
            severity = "ERROR" if rule in ("N1", "N3", "N5", "N6") else "WARNING"
            marker = "❌" if severity == "ERROR" else "⚠️"
            rule_names = {
                "N1": "item↔price binding",
                "N2": "mixed clause",
                "N3": "balance fabrication", 
                "N4": "math narration",
                "N5": "discount fabrication",
                "N6": "discount reason missing",
            }
            print(f"  {marker} {rule} ({rule_names[rule]}): {count} ({severity})")
        
        print()
        print(f"Hard rejects (ERROR):     {results['error_count']} samples")
        print(f"Flagged for review (WARN): {results['warning_count']} samples")
        print(f"Clean:                     {results['clean_count']} samples")
        print("=" * 60)
        
        # Show first 5 ERROR violations as examples
        errors = [v for v in results["all_violations"] if v["severity"] == "ERROR"]
        if errors:
            print(f"\nFirst {min(5, len(errors))} ERROR examples:")
            for v in errors[:5]:
                print(f"  [{v['rule']}] Sample #{v['sample_index']}: {v['message']}")
                print(f"         Response: \"{v['response_preview']}...\"")
                print()
    
    return results


# ---- STANDALONE USAGE ----

def lint_json_file(filepath: str, verbose: bool = True) -> dict:
    """
    Load a training JSON file and run the numeric authority linter.
    
    Supports both:
    - List of dicts (standard format)
    - JSONL format (one JSON per line)
    """
    filepath = Path(filepath)
    
    if filepath.suffix == '.jsonl':
        samples = []
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line:
                    samples.append(json.loads(line))
    else:
        with open(filepath) as f:
            samples = json.load(f)
    
    print(f"Loaded {len(samples)} samples from {filepath.name}")
    return lint_dataset_numeric(samples, verbose=verbose)


# Example usage (uncomment to run):
# results = lint_json_file("whisper_P6_FINAL_v2.json")
# 
# # Get list of samples that need to be removed/fixed:
# bad_indices = results["error_sample_indices"]
# print(f"\n{len(bad_indices)} samples need fixing or removal")

print("✅ Numeric Authority Linter defined (6 rules: N1-N6)")
print("   Run: lint_json_file('your_data.json')")
print("   Or:  lint_dataset_numeric(samples_list)")
