#!/usr/bin/env python3
"""Minify a CSS file in place, or write to a second path.

    python3 tools/minify_css.py _site/assets/style.css
    python3 tools/minify_css.py assets/style.css /tmp/style.min.css

Run by the deploy workflow on the published copy only. The source in git stays
readable. Only comments and insignificant whitespace are removed; strings and
url(...) contents are kept byte for byte. Spaces inside calc() and around
descendant combinators are kept, because removing them changes the meaning.
"""
import re
import sys


def minify(css):
    out = []
    i, n = 0, len(css)
    paren = 0
    pending_space = False

    def last():
        return out[-1][-1] if out else ""

    def emit(tok):
        nonlocal pending_space
        if pending_space and out:
            prev = last()
            first = tok[0]
            drop_before = first in "{};,>~)!" or (first == "+" and paren == 0)
            drop_after = prev in "{};,>~(" or (prev == "+" and paren == 0)
            # Space after a colon is never needed in a declaration or a feature
            # query; space before a colon is (".a :hover" differs from ".a:hover").
            if prev == ":":
                drop_after = True
            if not (drop_before or drop_after):
                out.append(" ")
        pending_space = False
        out.append(tok)

    while i < n:
        c = css[i]
        if css.startswith("/*", i):
            j = css.find("*/", i + 2)
            i = n if j == -1 else j + 2
            pending_space = True if out else False
            continue
        if c in " \t\r\n\f":
            pending_space = True
            i += 1
            continue
        if c in "\"'":
            j = i + 1
            while j < n and css[j] != c:
                j += 2 if css[j] == "\\" else 1
            emit(css[i : j + 1])
            i = j + 1
            continue
        if css.startswith("url(", i):
            j = css.find(")", i)
            body = css[i + 4 : j].strip()
            emit("url(" + body + ")")
            i = j + 1
            continue
        if c == "(":
            paren += 1
        elif c == ")":
            paren = max(0, paren - 1)
        if c == ";":
            # A semicolon right before } is redundant.
            k = i + 1
            while k < n and css[k] in " \t\r\n\f":
                k += 1
            if k < n and css[k] == "}":
                i = k
                pending_space = False
                continue
        emit(c)
        i += 1
    return "".join(out).strip()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else src
    with open(src, encoding="utf-8") as f:
        original = f.read()
    result = minify(original)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(result)
    print("%s: %d -> %d bytes" % (dst, len(original.encode()), len(result.encode())))


if __name__ == "__main__":
    main()
