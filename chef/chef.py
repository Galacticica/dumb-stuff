import random
import re
import sys

LIQUID_MEASURES = {"ml", "l", "dash", "dashes"}

INGREDIENT_RE = re.compile(
    r"^(?:(\d+)\s+)?(?:(?:heaped|level)\s+)?"
    r"(?:(g|kg|pinch(?:es)?|ml|l|dash(?:es)?|cups?|teaspoons?|tablespoons?)\s+)?"
    r"(.+)$",
    re.IGNORECASE,
)

BOWL = r"(?:the\s+)?(?:(\d+)(?:st|nd|rd|th)\s+)?mixing\s+bowl"
DISH = r"(?:the\s+)?(?:(\d+)(?:st|nd|rd|th)\s+)?baking\s+dish"


class ChefError(Exception):
    pass


class Recipe:
    def __init__(self, title):
        self.title = title
        self.ingredients = {}  # name -> (initial value or None, is_liquid)
        self.serves = None
        self.stmts = []


def strip_the(name):
    return name[4:] if name.startswith("the ") else name


def parse_file(text):
    lines = [line.strip() for line in text.splitlines()]
    n = len(lines)
    recipes = []

    def skip_blank(i):
        while i < n and not lines[i]:
            i += 1
        return i

    i = skip_blank(0)
    while i < n:
        recipe = Recipe(lines[i].rstrip(".").strip())
        i += 1
        while i < n and lines[i].lower() != "ingredients.":
            i += 1
        if i == n:
            raise ChefError(f"recipe '{recipe.title}' has no Ingredients section")
        i += 1
        while i < n and lines[i].lower() != "method.":
            line = lines[i]
            i += 1
            low = line.lower()
            if not line or low.startswith("cooking time") or low.startswith("pre-heat oven"):
                continue
            m = INGREDIENT_RE.match(line)
            qty, measure, name = m.group(1), m.group(2), m.group(3)
            value = int(qty) if qty else None
            liquid = bool(measure) and measure.lower() in LIQUID_MEASURES
            recipe.ingredients[name.strip().lower()] = (value, liquid)
        if i == n:
            raise ChefError(f"recipe '{recipe.title}' has no Method section")
        i += 1
        method_lines = []
        while i < n and lines[i] and not re.fullmatch(r"serves\s+\d+\.?", lines[i], re.IGNORECASE):
            method_lines.append(lines[i])
            i += 1
        j = skip_blank(i)
        if j < n:
            m = re.fullmatch(r"serves\s+(\d+)\.?", lines[j], re.IGNORECASE)
            if m:
                recipe.serves = int(m.group(1))
                j += 1
                i = j
        sentences = [s.strip() for s in " ".join(method_lines).split(".") if s.strip()]
        compile_stmts(recipe, sentences)
        recipes.append(recipe)
        i = skip_blank(i)
    if not recipes:
        raise ChefError("no recipes found")
    return recipes


def parse_stmt(s, recipe):
    def m(pattern):
        return re.fullmatch(pattern, s)

    r = m(r"take (.+?) from (?:the )?refrigerator")
    if r:
        return {"op": "take", "ing": strip_the(r.group(1))}
    r = m(rf"put (.+?) into {BOWL}")
    if r:
        return {"op": "put", "ing": strip_the(r.group(1)), "bowl": r.group(2)}
    r = m(rf"fold (.+?) into {BOWL}")
    if r:
        return {"op": "fold", "ing": strip_the(r.group(1)), "bowl": r.group(2)}
    r = m(rf"add (?:the )?dry ingredients(?: to {BOWL})?")
    if r:
        return {"op": "add_dry", "bowl": r.group(1)}
    r = m(rf"add (.+?)(?: to {BOWL})?")
    if r:
        return {"op": "arith", "fn": "add", "ing": strip_the(r.group(1)), "bowl": r.group(2)}
    r = m(rf"remove (.+?)(?: from {BOWL})?")
    if r:
        return {"op": "arith", "fn": "remove", "ing": strip_the(r.group(1)), "bowl": r.group(2)}
    r = m(rf"combine (.+?)(?: into {BOWL})?")
    if r:
        return {"op": "arith", "fn": "combine", "ing": strip_the(r.group(1)), "bowl": r.group(2)}
    r = m(rf"divide (.+?)(?: into {BOWL})?")
    if r:
        return {"op": "arith", "fn": "divide", "ing": strip_the(r.group(1)), "bowl": r.group(2)}
    r = m(rf"liquefy (?:the )?contents of {BOWL}")
    if r:
        return {"op": "liquefy_bowl", "bowl": r.group(1)}
    r = m(r"liquefy (.+)")
    if r:
        return {"op": "liquefy_ing", "ing": strip_the(r.group(1))}
    r = m(rf"stir (?:{BOWL} )?for (\d+) minutes?")
    if r:
        return {"op": "stir_n", "bowl": r.group(1), "n": int(r.group(2))}
    r = m(rf"stir (.+?) into {BOWL}")
    if r:
        return {"op": "stir_ing", "ing": strip_the(r.group(1)), "bowl": r.group(2)}
    r = m(rf"mix (?:{BOWL} )?well")
    if r:
        return {"op": "mix", "bowl": r.group(1)}
    r = m(rf"clean {BOWL}")
    if r:
        return {"op": "clean", "bowl": r.group(1)}
    r = m(rf"pour (?:the )?contents of {BOWL} into {DISH}")
    if r:
        return {"op": "pour", "bowl": r.group(1), "dish": r.group(2)}
    if m(r"set aside"):
        return {"op": "set_aside", "jump": None}
    r = m(r"serve with (.+)")
    if r:
        return {"op": "serve", "recipe": r.group(1)}
    r = m(r"refrigerate(?: for (\d+) hours?)?")
    if r:
        return {"op": "refrigerate", "hours": int(r.group(1)) if r.group(1) else None}
    r = m(r"(\w+)(?: (?:the )?(.+?))? until (\w+)")
    if r:
        return {"op": "loop_end", "ing": r.group(2), "verbed": r.group(3), "start": None}
    r = m(r"(\w+) (?:the )?(.+)")
    if r and r.group(2) in recipe.ingredients:
        return {"op": "loop_start", "verb": r.group(1), "ing": r.group(2), "end": None}
    raise ChefError(f"cannot parse statement '{s}' in recipe '{recipe.title}'")


def compile_stmts(recipe, sentences):
    stmts = [parse_stmt(re.sub(r"\s+", " ", s.lower()), recipe) for s in sentences]
    stack = []
    pending_asides = {}
    for idx, st in enumerate(stmts):
        if st["op"] == "loop_start":
            stack.append(idx)
            pending_asides[idx] = []
        elif st["op"] == "set_aside":
            if not stack:
                raise ChefError(f"'set aside' outside a loop in '{recipe.title}'")
            pending_asides[stack[-1]].append(idx)
        elif st["op"] == "loop_end":
            if not stack:
                raise ChefError(f"loop end with no matching start in '{recipe.title}'")
            start = stack.pop()
            verb = stmts[start]["verb"]
            if st["verbed"] not in (verb + "d", verb + "ed"):
                raise ChefError(
                    f"loop verb mismatch in '{recipe.title}': "
                    f"'{verb}' vs 'until {st['verbed']}'"
                )
            stmts[start]["end"] = idx
            st["start"] = start
            for aside in pending_asides.pop(start):
                stmts[aside]["jump"] = idx + 1
    if stack:
        raise ChefError(f"unclosed loop in '{recipe.title}'")
    recipe.stmts = stmts


def stdin_tokens():
    for line in sys.stdin:
        yield from line.split()


def output_dishes(dishes, count, out):
    for d in range(1, count + 1):
        dish = dishes.get(d, [])
        while dish:
            value, liquid = dish.pop()
            out.append(chr(value) if liquid else str(value) + " ")


def execute(recipe, book, bowls, dishes, out, tokens, depth=0):
    if depth > 900:
        raise ChefError("too many nested 'serve with' calls")
    ings = {name: [value, liquid] for name, (value, liquid) in recipe.ingredients.items()}

    def value_of(name):
        if name not in ings:
            raise ChefError(f"unknown ingredient '{name}' in '{recipe.title}'")
        if ings[name][0] is None:
            raise ChefError(f"ingredient '{name}' used before it has a value in '{recipe.title}'")
        return ings[name][0]

    def bowl(key):
        return bowls.setdefault(int(key) if key else 1, [])

    def dish(key):
        return dishes.setdefault(int(key) if key else 1, [])

    def top_of(b):
        if not b:
            raise ChefError(f"mixing bowl is empty in '{recipe.title}'")
        return b

    pc = 0
    while pc < len(recipe.stmts):
        st = recipe.stmts[pc]
        op = st["op"]
        if op == "take":
            token = next(tokens, None)
            if token is None:
                raise ChefError("ran out of input for 'take from refrigerator'")
            ings.setdefault(st["ing"], [None, False])[0] = int(token)
        elif op == "put":
            bowl(st["bowl"]).append((value_of(st["ing"]), ings[st["ing"]][1]))
        elif op == "fold":
            b = top_of(bowl(st["bowl"]))
            value, _ = b.pop()
            ings.setdefault(st["ing"], [None, False])[0] = value
        elif op == "arith":
            b = top_of(bowl(st["bowl"]))
            top, liquid = b[-1]
            x = value_of(st["ing"])
            if st["fn"] == "add":
                top += x
            elif st["fn"] == "remove":
                top -= x
            elif st["fn"] == "combine":
                top *= x
            else:
                top //= x
            b[-1] = (top, liquid)
        elif op == "add_dry":
            total = sum(v for v, liq in ings.values() if not liq and v is not None)
            bowl(st["bowl"]).append((total, False))
        elif op == "liquefy_ing":
            if st["ing"] not in ings:
                raise ChefError(f"unknown ingredient '{st['ing']}' in '{recipe.title}'")
            ings[st["ing"]][1] = True
        elif op == "liquefy_bowl":
            b = bowl(st["bowl"])
            b[:] = [(v, True) for v, _ in b]
        elif op in ("stir_n", "stir_ing"):
            b = bowl(st["bowl"])
            if b:
                places = st["n"] if op == "stir_n" else value_of(st["ing"])
                item = b.pop()
                b.insert(max(0, len(b) - places), item)
        elif op == "mix":
            random.shuffle(bowl(st["bowl"]))
        elif op == "clean":
            bowl(st["bowl"]).clear()
        elif op == "pour":
            dish(st["dish"]).extend(bowl(st["bowl"]))
        elif op == "loop_start":
            if value_of(st["ing"]) == 0:
                pc = st["end"] + 1
                continue
        elif op == "loop_end":
            if st["ing"]:
                if st["ing"] not in ings:
                    raise ChefError(f"unknown ingredient '{st['ing']}' in '{recipe.title}'")
                ings[st["ing"]][0] = value_of(st["ing"]) - 1
            pc = st["start"]
            continue
        elif op == "set_aside":
            pc = st["jump"]
            continue
        elif op == "serve":
            aux = book.get(st["recipe"])
            if aux is None:
                raise ChefError(f"no auxiliary recipe named '{st['recipe']}'")
            sub_bowls = {k: list(v) for k, v in bowls.items()}
            sub_dishes = {k: list(v) for k, v in dishes.items()}
            execute(aux, book, sub_bowls, sub_dishes, out, tokens, depth + 1)
            bowls.setdefault(1, []).extend(sub_bowls.get(1, []))
        elif op == "refrigerate":
            if st["hours"]:
                output_dishes(dishes, st["hours"], out)
            return
        pc += 1
    if recipe.serves:
        output_dishes(dishes, recipe.serves, out)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python chef.py <recipe.chef>")
    with open(sys.argv[1], encoding="utf-8") as f:
        recipes = parse_file(f.read())
    book = {r.title.lower(): r for r in recipes}
    out = []
    try:
        execute(recipes[0], book, {}, {}, out, stdin_tokens())
    except ChefError as e:
        sys.exit(f"chef error: {e}")
    finally:
        text = "".join(out).rstrip()
        if text:
            print(text)


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
