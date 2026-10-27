from hashlib import md5, sha256
import re

from cyberlab.assessment_checks import combined_status

STRING_OPERATORS = {"string_equal", "string_diff", "string_contains", "string_start", "string_end"}
INTEGER_OPERATORS = {"integer_equal", "integer_greater", "integer_less"}
HASH_OPERATORS = {"hash_equal"}
COMPARE_OPERATORS = STRING_OPERATORS | INTEGER_OPERATORS | HASH_OPERATORS

def integer_value(value):
    if type(value) is int:
        number = value
    elif isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]{1,19}", value.strip()):
        number = int(value)
    else:
        raise ValueError("Comparison requires a signed 64-bit integer")
    if not -(2 ** 63) <= number < 2 ** 63:
        raise ValueError("Comparison requires a signed 64-bit integer")
    return number

def evaluate_boolean_expression(expr, values):
    expr = re.sub(r"\band_not\b", "and not", expr, flags=re.I)
    expr = re.sub(r"\bor_not\b", "or not", expr, flags=re.I)
    token_pattern = re.compile(r"\(|\)|\b(?:and|or|not|true|false)\b|[a-z0-9][a-z0-9_-]*", re.I)
    tokens = token_pattern.findall(expr)

    stripped = re.sub(r"\s+", "", expr)
    reconstructed = "".join(tokens)
    if stripped.lower() != reconstructed.lower():
        raise ValueError("Invalid character in boolean expression")

    pos = 0

    def peek():
        return tokens[pos].lower() if pos < len(tokens) else None

    def consume():
        nonlocal pos
        t = tokens[pos]
        pos += 1
        return t

    def parse_expr():
        return parse_or()

    def parse_or():
        left = parse_and()
        while peek() == "or":
            consume()
            right = parse_and()
            if left is True or right is True:
                left = True
            elif left is False and right is False:
                left = False
            else:
                left = None
        return left

    def parse_and():
        left = parse_not()
        while peek() == "and":
            consume()
            right = parse_not()
            if left is False or right is False:
                left = False
            elif left is True and right is True:
                left = True
            else:
                left = None
        return left

    def parse_not():
        if peek() == "not":
            consume()
            sub = parse_not()
            if sub is True:
                return False
            elif sub is False:
                return True
            else:
                return None
        return parse_primary()

    def parse_primary():
        nonlocal pos
        p = peek()
        if p == "(":
            consume()
            res = parse_expr()
            if peek() != ")":
                raise ValueError("Mismatched parentheses")
            consume()
            return res
        elif p == "true":
            consume()
            return True
        elif p == "false":
            consume()
            return False
        elif p and re.fullmatch(r"[a-z0-9][a-z0-9_-]*", p):
            ident = consume()
            if ident not in values:
                raise KeyError(f"Unknown identifier {ident}")
            return values[ident]
        else:
            raise ValueError(f"Unexpected token {p}")

    res = parse_expr()
    if pos < len(tokens):
        raise ValueError(f"Unexpected trailing token {tokens[pos]}")
    return res

def _comparison(goal, results):
    operands = [results.get(goal.result)]
    if goal.other:
        operands.append(results.get(goal.other))
    if any(item is None or item.get("status") not in {"PASS", "FAIL"} for item in operands):
        return "ERROR", "A comparison result could not be evaluated"
    if any(item.get("value") is None for item in operands):
        return "FAIL", "The selected value was not found"
    left = operands[0]["value"]
    right = operands[1]["value"] if goal.other else goal.expected
    if goal.operator in INTEGER_OPERATORS:
        if not goal.other:
            try:
                right = integer_value(right)
            except ValueError:
                return "ERROR", "The expected value is not a signed 64-bit integer"
        try:
            left, right = integer_value(left), integer_value(right)
        except ValueError:
            return "FAIL", "The captured value is not a signed 64-bit integer"
        passed = {"integer_equal": left == right, "integer_greater": left > right,
                  "integer_less": left < right}[goal.operator]
    elif goal.operator in STRING_OPERATORS:
        if not all(type(value) in {str, int, bool} for value in (left, right)):
            return "ERROR", "String comparison requires scalar values"
        left, right = (str(value).lower() if type(value) is bool else str(value)
                       for value in (left, right))
        passed = {"string_equal": left == right, "string_diff": left != right,
                  "string_contains": right in left, "string_start": left.startswith(right),
                  "string_end": left.endswith(right)}[goal.operator]
    elif goal.operator in HASH_OPERATORS:
        if not all(type(value) in {str, int, bool} for value in (left, right)):
            return "ERROR", "Hash comparison requires scalar values"
        left_str = str(left) if left is not None else ""
        right_str = str(right).strip()
        if len(right_str) == 64:
            digest = sha256(left_str.encode("utf-8")).hexdigest()
        else:
            digest = md5(left_str.encode("utf-8")).hexdigest()
        passed = (digest.lower() == right_str.lower())
    else:
        return "ERROR", "Unsupported comparison operator"
    return ("PASS", "Comparison satisfied") if passed else ("FAIL", "Comparison not satisfied")

def _boolean_evaluation(goal, results, goals_by_id):
    if not goal.expression or not isinstance(goal.expression, str):
        return "ERROR", "Boolean goal requires an expression"
    values = {}
    for ref in goal.results:
        if ref in goals_by_id:
            st = goals_by_id[ref].get("status")
            values[ref] = True if st == "PASS" else False if st == "FAIL" else None
        elif ref in results:
            st = results[ref].get("status")
            values[ref] = True if st == "PASS" else False if st == "FAIL" else None
        else:
            values[ref] = None
    try:
        outcome = evaluate_boolean_expression(goal.expression, values)
        if outcome is True:
            return "PASS", "Boolean expression satisfied"
        elif outcome is False:
            return "FAIL", "Boolean expression not satisfied"
        else:
            return "ERROR", "Some referenced conditions could not be evaluated"
    except Exception as error:
        return "ERROR", str(error)

def check_goal(goal, results, goals_by_id=None):
    report = {"id": goal.id, "mode": goal.mode, "type": goal.goal_type,
              "results": list(goal.results), "description": goal.description}
    if goal.expression:
        report["expression"] = goal.expression
    if goal.goal_type == "compare":
        status, message = _comparison(goal, results)
    elif goal.goal_type == "count":
        if goal.operator != "count_greater" or type(goal.threshold) is not int or not 0 <= goal.threshold <= 64:
            status, message = "ERROR", "Invalid count threshold or operator"
        else:
            statuses = [results.get(identifier, {}).get("status", "ERROR") for identifier in goal.results]
            passed = statuses.count("PASS")
            unknown = sum(item not in {"PASS", "FAIL"} for item in statuses)
            status = "PASS" if passed > goal.threshold else "ERROR" if passed + unknown > goal.threshold else "FAIL"
            message = "Some results could not be evaluated" if status == "ERROR" else f"{passed} of {len(statuses)} results passed"
            report["value"] = passed
    elif goal.goal_type == "boolean":
        status, message = _boolean_evaluation(goal, results, goals_by_id or {})
    elif goal.goal_type == "group":
        status = combined_status([results.get(identifier, {}).get("status", "ERROR") for identifier in goal.results], goal.mode)
        message = "Results combined using " + goal.mode
    else:
        status, message = "ERROR", "Unsupported goal type"
    return {**report, "status": status, "message": message}
