"""
OpenBenchML — Learn with Interactive Labs
==========================================

A third learning mode (alongside Concepts and Project) that gives each
concept a LIVE EDITOR + LIVE PREVIEW.  The user changes a value (e.g.
box-shadow: 2px → 10px) and the output updates instantly in the browser.

Routes:
    GET /learn/labs             -> overview (all labs grouped by category)
    GET /learn/labs/{slug}      -> single lab page with editor + preview

Lab categories:
    Python    -> 25 labs  (variables, loops, functions, lists, dicts,
                            if/else, comprehensions, classes, exceptions)
    HTML      -> 12 labs  (tags, forms, links, images, semantic, tables)
    CSS       -> 18 labs  (classic CSS — colors, borders, box-shadow,
                            margin/padding, font, display, position,
                            flexbox, grid, transitions, hover, z-index)
    FastAPI   -> 10 labs  (routes, path params, query params, pydantic,
                            templates, static files, deps, websocket)

Lab structure:
    {
      "slug": "css-box-shadow",
      "category": "CSS",
      "title": "box-shadow — give a card depth",
      "language": "css",  # css | html | python | fastapi
      "summary": "...",
      "starter_code": "...",
      "html_template": "...",  # for CSS labs — the HTML to render
      "explanation": "...",
      "try_changes": [
         ("Change 2px to 10px", "the shadow becomes more spread out"),
         ("Change 'black' to 'rgba(0,0,0,0.5)'", "the shadow becomes semi-transparent"),
      ],
    }

Execution model:
    css/html   -> live iframe srcdoc (instant, no server round-trip)
    python     -> POST to /api/notebook/cell (server-side kernel)
    fastapi    -> client-side simulator (shows route + fake request/response)
"""

from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional

from app.config import APP_NAME, APP_VERSION, templates
from app.routes.auth import get_current_user_from_cookie
from app.database.db import SessionLocal

router = APIRouter()


# ═══════════════════════════════════════════════════════════════════════════
#  CSS LABS — classic CSS (no Tailwind, no framework)
# ═══════════════════════════════════════════════════════════════════════════

_CSS_LABS = [
    {
        "slug": "css-color",
        "category": "CSS",
        "title": "color — change the text color",
        "language": "css",
        "summary": "The most basic CSS property. Change the color value and watch the text recolor instantly.",
        "starter_code": ".card {\n  color: #a0c000;\n  background: white;\n  padding: 20px;\n  border: 1px solid #ddd;\n  border-radius: 8px;\n}",
        "html_template": "<div class=\"card\">Hello world!<br>This text uses the <code>color</code> property from the CSS on the left.</div>",
        "explanation": (
            "color sets the text color. Accepts named colors (red, blue), hex (#a0c000), "
            "rgb(160,192,0), or rgba(160,192,0,0.5) for semi-transparent. The value is "
            "inherited — child elements get the parent's color unless overridden."
        ),
        "try_changes": [
            ("Change #a0c000 to red", "text becomes red"),
            ("Change to rgb(255, 0, 0)", "same red, different syntax"),
            ("Add color: blue inside .card", "overrides to blue"),
        ],
    },
    {
        "slug": "css-background",
        "category": "CSS",
        "title": "background — fill the element's box",
        "language": "css",
        "summary": "background-color fills the box. background-image uses an image. background gradient blends colors.",
        "starter_code": ".card {\n  background: linear-gradient(135deg, #a0c000, #58a6ff);\n  color: white;\n  padding: 30px;\n  border-radius: 10px;\n}",
        "html_template": "<div class=\"card\">Gradient background!<br>Try changing the colors or angle.</div>",
        "explanation": (
            "background-color is a flat color. background-image: url(...) tiles an image. "
            "linear-gradient(angle, color1, color2) blends two colors at an angle. The angle "
            "is degrees: 0deg = up, 90deg = right, 135deg = down-right (the diagonal)."
        ),
        "try_changes": [
            ("Change 135deg to 0deg", "gradient goes bottom-to-top"),
            ("Change 135deg to 90deg", "gradient goes left-to-right"),
            ("Change #58a6ff to #f85149", "second color becomes red"),
            ("Replace the whole background with: background: #f5f5f5;", "flat grey background"),
        ],
    },
    {
        "slug": "css-border",
        "category": "CSS",
        "title": "border — outline the element",
        "language": "css",
        "summary": "border needs 3 values: width, style, color. Change any of the three.",
        "starter_code": ".card {\n  border: 2px solid #a0c000;\n  padding: 20px;\n  background: white;\n  border-radius: 8px;\n}",
        "html_template": "<div class=\"card\">This card has a border.<br>Try changing 2px, solid, or the color.</div>",
        "explanation": (
            "border: <width> <style> <color> is the shorthand. width is in px. style can be "
            "solid, dashed, dotted, double, groove, ridge, none. You can also set per-side: "
            "border-top, border-right, border-bottom, border-left."
        ),
        "try_changes": [
            ("Change 2px to 10px", "border becomes much thicker"),
            ("Change solid to dashed", "border becomes dashes"),
            ("Change solid to dotted", "border becomes dots"),
            ("Change solid to double", "two parallel lines"),
            ("Change #a0c000 to red", "border becomes red"),
        ],
    },
    {
        "slug": "css-box-shadow",
        "category": "CSS",
        "title": "box-shadow — give the card depth",
        "language": "css",
        "summary": "The example from your message. 5 values: x-offset, y-offset, blur, spread, color.",
        "starter_code": ".card {\n  box-shadow: 2px 2px 8px rgba(0,0,0,0.2);\n  padding: 30px;\n  background: white;\n  border-radius: 10px;\n  margin: 40px;\n}",
        "html_template": "<div class=\"card\">This card has a box-shadow.<br>Try changing 2px to 10px — the shadow moves further down-right.</div>",
        "explanation": (
            "box-shadow syntax: <x-offset> <y-offset> <blur> <spread> <color>. "
            "x-offset: positive = right, negative = left. "
            "y-offset: positive = down, negative = up. "
            "blur: 0 = sharp edge, larger = more diffused. "
            "spread: positive = grows, negative = shrinks. "
            "color: use rgba() to make the shadow semi-transparent (much more realistic)."
        ),
        "try_changes": [
            ("Change the first 2px to 10px", "shadow moves further to the right"),
            ("Change the second 2px to 10px", "shadow moves further down"),
            ("Change 8px (blur) to 30px", "shadow becomes much softer"),
            ("Change rgba(0,0,0,0.2) to rgba(0,0,0,0.8)", "shadow becomes darker"),
            ("Add 'inset ' at the start (before 2px)", "shadow goes INSIDE the card"),
            ("Use negative: -5px -5px 10px rgba(0,0,0,0.3)", "shadow goes up-left (light source from bottom-right)"),
        ],
    },
    {
        "slug": "css-margin-padding",
        "category": "CSS",
        "title": "margin vs padding — the box model",
        "language": "css",
        "summary": "margin is OUTSIDE the border (space between elements). padding is INSIDE the border (space between border and content).",
        "starter_code": ".card {\n  margin: 20px;\n  padding: 20px;\n  background: #f5f5f5;\n  border: 2px solid #a0c000;\n  border-radius: 6px;\n}",
        "html_template": "<div>Other content above</div>\n<div class=\"card\">This is the card content.<br>padding = space INSIDE the border.<br>margin = space OUTSIDE the border.</div>\n<div>Other content below</div>",
        "explanation": (
            "Every HTML element is a box with 4 layers (outside-in): margin, border, padding, content. "
            "margin: space between this box and other boxes. "
            "padding: space between the border and the content. "
            "background fills the padding area too — so larger padding = bigger colored area. "
            "margin is transparent; padding takes the background color."
        ),
        "try_changes": [
            ("Change margin: 20px to margin: 50px", "more space around the card"),
            ("Change padding: 20px to padding: 50px", "card grows, content has more breathing room"),
            ("Change margin to 0px", "card touches the surrounding content"),
            ("Use margin: 20px 50px (2 values)", "20px top/bottom, 50px left/right"),
            ("Use margin: 10px 20px 30px 40px (4 values)", "top right bottom left (clockwise)"),
        ],
    },
    {
        "slug": "css-font",
        "category": "CSS",
        "title": "font-family, font-size, font-weight — typography",
        "language": "css",
        "summary": "Change the typeface, size, and boldness. Use system fonts for instant loading.",
        "starter_code": ".card {\n  font-family: 'Georgia', serif;\n  font-size: 18px;\n  font-weight: 400;\n  line-height: 1.6;\n  padding: 20px;\n  background: white;\n  border: 1px solid #ddd;\n  border-radius: 6px;\n}",
        "html_template": "<div class=\"card\">\n  <h3>Typography matters</h3>\n  <p>The quick brown fox jumps over the lazy dog. 0123456789 — notice the numbers.</p>\n</div>",
        "explanation": (
            "font-family takes a list — the browser uses the first one installed. Common stacks: "
            "'Georgia, serif' (classic), 'Arial, sans-serif' (modern), 'Courier New, monospace' (code). "
            "font-size: 16px is the browser default. Use rem for relative sizing (1rem = root font size). "
            "font-weight: 400 = normal, 700 = bold. line-height: 1.6 means 1.6x the font size — improves readability."
        ),
        "try_changes": [
            ("Change 'Georgia', serif to 'Arial', sans-serif", "modern sans-serif look"),
            ("Change font-size to 24px", "text becomes larger"),
            ("Change font-weight to 700", "text becomes bold"),
            ("Change line-height to 1.2", "lines get closer together (worse readability)"),
            ("Change line-height to 2.0", "lines get further apart (better readability)"),
        ],
    },
    {
        "slug": "css-display",
        "category": "CSS",
        "title": "display — block, inline, none",
        "language": "css",
        "summary": "Controls how an element fits in the page flow. block = full width. inline = only as wide as content. none = hidden.",
        "starter_code": ".box {\n  display: block;\n  background: #a0c000;\n  color: white;\n  padding: 10px;\n  margin: 5px;\n}",
        "html_template": "<span class=\"box\">Box 1</span>\n<span class=\"box\">Box 2</span>\n<span class=\"box\">Box 3</span>\n<p>Notice how the spans (normally inline) behave based on the display value.</p>",
        "explanation": (
            "Every HTML element has a default display: div/p/h1 = block, span/a/strong = inline. "
            "display: block — element takes full width, starts on a new line. "
            "display: inline — element takes only its content width, stays in line. "
            "display: none — element is removed from the page entirely (no space). "
            "display: inline-block — best of both: stays in line BUT accepts width/height."
        ),
        "try_changes": [
            ("Change display: block to display: inline", "boxes shrink to content and stay in a row"),
            ("Change to display: none", "boxes disappear completely"),
            ("Change to display: inline-block", "boxes stay in a row but keep their padding/width"),
            ("Add width: 200px after display: block", "block elements respect width"),
        ],
    },
    {
        "slug": "css-position",
        "category": "CSS",
        "title": "position — static, relative, absolute, fixed",
        "language": "css",
        "summary": "Controls how an element is positioned. The most confusing CSS property — play with it.",
        "starter_code": ".container {\n  position: relative;\n  background: #f5f5f5;\n  padding: 60px;\n  border: 1px solid #ddd;\n}\n.badge {\n  position: absolute;\n  top: 10px;\n  right: 10px;\n  background: #a0c000;\n  color: white;\n  padding: 5px 10px;\n  border-radius: 4px;\n}",
        "html_template": "<div class=\"container\">\n  <div class=\"badge\">NEW</div>\n  This is the container. The badge is positioned ABSOLUTELY relative to it.\n</div>",
        "explanation": (
            "static (default) — normal flow, top/left have no effect. "
            "relative — normal flow, but top/left/right/bottom OFFSET it from its normal position. "
            "absolute — removed from flow, positioned relative to the NEAREST positioned ancestor "
            "(an ancestor with position: relative/absolute/fixed). "
            "fixed — positioned relative to the viewport (stays put on scroll). "
            "Always set position: relative on the parent when using position: absolute on a child."
        ),
        "try_changes": [
            ("Change container position: relative to position: static", "badge positions relative to <body> instead of container"),
            ("Change top: 10px to bottom: 10px", "badge moves to bottom-right"),
            ("Change right: 10px to left: 10px", "badge moves to top-left"),
            ("Change .badge position: absolute to position: fixed", "badge stays even when you scroll (won't show much here, but try in a real page)"),
        ],
    },
    {
        "slug": "css-flexbox",
        "category": "CSS",
        "title": "flexbox — the modern layout system",
        "language": "css",
        "summary": "display: flex turns a parent into a flex container. justify-content and align-items control alignment.",
        "starter_code": ".container {\n  display: flex;\n  justify-content: center;\n  align-items: center;\n  gap: 10px;\n  background: #f5f5f5;\n  padding: 20px;\n  min-height: 120px;\n}\n.box {\n  background: #a0c000;\n  color: white;\n  padding: 15px;\n  border-radius: 6px;\n}",
        "html_template": "<div class=\"container\">\n  <div class=\"box\">1</div>\n  <div class=\"box\">2</div>\n  <div class=\"box\">3</div>\n</div>",
        "explanation": (
            "display: flex on the PARENT makes children flex items. "
            "justify-content: main-axis alignment (left-right by default). "
            "  flex-start (default) | center | flex-end | space-between | space-around. "
            "align-items: cross-axis alignment (top-bottom by default). "
            "  stretch (default) | center | flex-start | flex-end. "
            "gap: space between items. "
            "flex-direction: row (default) | column — changes which axis is main vs cross."
        ),
        "try_changes": [
            ("Change justify-content: center to space-between", "boxes spread to edges with space between"),
            ("Change to space-around", "equal space AROUND each box (smaller gaps at edges)"),
            ("Change to flex-end", "boxes push to the right"),
            ("Change align-items: center to flex-start", "boxes stick to the top"),
            ("Add flex-direction: column;", "boxes stack vertically — main axis is now top-to-bottom"),
            ("Change gap: 10px to gap: 30px", "more space between boxes"),
        ],
    },
    {
        "slug": "css-grid",
        "category": "CSS",
        "title": "grid — 2D layouts",
        "language": "css",
        "summary": "display: grid creates a 2D grid. grid-template-columns defines columns. The most powerful CSS layout.",
        "starter_code": ".container {\n  display: grid;\n  grid-template-columns: 1fr 1fr 1fr;\n  gap: 10px;\n  background: #f5f5f5;\n  padding: 20px;\n}\n.box {\n  background: #a0c000;\n  color: white;\n  padding: 20px;\n  text-align: center;\n  border-radius: 6px;\n}",
        "html_template": "<div class=\"container\">\n  <div class=\"box\">1</div>\n  <div class=\"box\">2</div>\n  <div class=\"box\">3</div>\n  <div class=\"box\">4</div>\n  <div class=\"box\">5</div>\n  <div class=\"box\">6</div>\n</div>",
        "explanation": (
            "grid-template-columns defines the column tracks. "
            "  1fr 1fr 1fr = 3 equal columns (fr = fraction of available space). "
            "  200px 1fr = fixed 200px first column, flexible second. "
            "  repeat(3, 1fr) = same as 1fr 1fr 1fr. "
            "  repeat(auto-fit, minmax(150px, 1fr)) = responsive! As many columns as fit, each at least 150px. "
            "gap: space between rows AND columns. "
            "grid-template-rows: same syntax for rows."
        ),
        "try_changes": [
            ("Change 1fr 1fr 1fr to 1fr 2fr 1fr", "middle column is twice as wide"),
            ("Change to 200px 1fr", "first column fixed 200px, second takes the rest"),
            ("Change to repeat(2, 1fr)", "2 columns instead of 3 — items wrap to 3 rows"),
            ("Change to repeat(auto-fit, minmax(120px, 1fr))", "responsive! resize your browser to see columns adjust"),
            ("Change gap: 10px to gap: 20px 5px", "20px row gap, 5px column gap"),
        ],
    },
    {
        "slug": "css-transition",
        "category": "CSS",
        "title": "transition — smooth animations",
        "language": "css",
        "summary": "transition: <property> <duration> <easing>. Makes changes animate instead of snapping.",
        "starter_code": ".card {\n  background: #a0c000;\n  color: white;\n  padding: 20px;\n  border-radius: 8px;\n  transition: background 0.3s ease, transform 0.3s ease;\n  cursor: pointer;\n}\n.card:hover {\n  background: #58a6ff;\n  transform: translateY(-5px);\n}",
        "html_template": "<div class=\"card\">Hover over me!<br>The background and position animate smoothly.</div>",
        "explanation": (
            "transition tells the browser WHICH properties to animate and HOW LONG. "
            "  transition: <property> <duration> <easing> <delay>. "
            "  property: which CSS prop to animate (background, transform, opacity, ...). "
            "  duration: how long (0.3s = 300ms). "
            "  easing: ease (default), linear, ease-in, ease-out, ease-in-out. "
            ":hover is a pseudo-class — applies when the mouse is over the element. "
            "The transition GOES ON THE BASE STATE, not on :hover — common beginner mistake."
        ),
        "try_changes": [
            ("Change 0.3s to 1s", "animation becomes much slower"),
            ("Change ease to linear", "animation has constant speed (feels less natural)"),
            ("Change transform: translateY(-5px) to scale(1.1)", "card grows 10% on hover instead of moving up"),
            ("Change to translateY(5px)", "card moves DOWN on hover"),
            ("Remove the transition line entirely", "changes happen instantly (no animation)"),
        ],
    },
    {
        "slug": "css-hover-z-index",
        "category": "CSS",
        "title": "z-index — stacking order",
        "language": "css",
        "summary": "z-index controls which element appears on top when they overlap. Higher = on top. Only works on positioned elements.",
        "starter_code": ".box {\n  position: absolute;\n  width: 100px;\n  height: 100px;\n  padding: 10px;\n  color: white;\n  border-radius: 6px;\n}\n.red    { background: #f85149; top: 0;   left: 0;   z-index: 1; }\n.green  { background: #3fb950; top: 30px; left: 30px; z-index: 2; }\n.blue   { background: #58a6ff; top: 60px; left: 60px; z-index: 3; }",
        "html_template": "<div style=\"position: relative; height: 200px;\">\n  <div class=\"box red\">red (z=1)</div>\n  <div class=\"box green\">green (z=2)</div>\n  <div class=\"box blue\">blue (z=3)</div>\n</div>",
        "explanation": (
            "z-index only works on positioned elements (position: relative/absolute/fixed/sticky). "
            "On static elements, z-index is ignored. "
            "Higher z-index = closer to the user (on top). "
            "Default z-index is 0 (or 'auto'). "
            "Modal dialogs typically use z-index: 1000+ to appear above everything. "
            "Inside a stacking context, only siblings compete — a child of a low-z-index parent cannot escape above a high-z-index sibling of the parent."
        ),
        "try_changes": [
            ("Change .red z-index: 1 to z-index: 10", "red jumps to the top"),
            ("Change .blue z-index: 3 to z-index: 0", "blue drops to the bottom"),
            ("Change .green z-index: 2 to z-index: -1", "green goes BEHIND the page background (becomes invisible)"),
        ],
    },
    {
        "slug": "css-border-radius",
        "category": "CSS",
        "title": "border-radius — round the corners",
        "language": "css",
        "summary": "Rounds each corner. One value = all corners. Four values = top-left, top-right, bottom-right, bottom-left.",
        "starter_code": ".card {\n  background: #a0c000;\n  color: white;\n  padding: 30px;\n  border-radius: 12px;\n  width: 200px;\n  height: 100px;\n}",
        "html_template": "<div class=\"card\">border-radius: 12px</div>",
        "explanation": (
            "border-radius accepts 1-4 values (clockwise from top-left): "
            "  1 value: same on all corners. "
            "  2 values: top-left+bottom-right, top-right+bottom-left. "
            "  4 values: top-left, top-right, bottom-right, bottom-left. "
            "Use 50% on a square element to make a perfect circle. "
            "You can also use 'border-top-left-radius' etc. for per-corner control. "
            "Elliptical corners: 'border-radius: 20px / 40px' (horizontal / vertical)."
        ),
        "try_changes": [
            ("Change 12px to 0px", "sharp corners"),
            ("Change 12px to 50%", "becomes an ellipse (because element is not square)"),
            ("Change to 50px 5px 50px 5px", "leaf-like shape"),
            ("Change to 20px / 40px", "elliptical corners (horizontal 20, vertical 40)"),
            ("Make width: 100px; height: 100px; and border-radius: 50%", "perfect circle"),
        ],
    },
    {
        "slug": "css-pseudo-classes",
        "category": "CSS",
        "title": ":hover, :focus, :active, :nth-child",
        "language": "css",
        "summary": "Pseudo-classes target elements based on state or position. Hover, focus, nth-child are the most common.",
        "starter_code": "li {\n  padding: 8px;\n  background: white;\n  border: 1px solid #ddd;\n  margin: 4px 0;\n  list-style: none;\n  border-radius: 4px;\n  transition: all 0.2s;\n}\nli:hover { background: #a0c000; color: white; }\nli:nth-child(odd) { background: #f5f5f5; }\nli:nth-child(odd):hover { background: #a0c000; color: white; }\nli:first-child { border-left: 4px solid #58a6ff; }\nli:last-child { font-weight: bold; }",
        "html_template": "<ul>\n  <li>First item</li>\n  <li>Second item</li>\n  <li>Third item</li>\n  <li>Fourth item</li>\n  <li>Fifth item</li>\n</ul>",
        "explanation": (
            ":hover — mouse is over the element. "
            ":focus — element has focus (e.g. an input you're typing in). "
            ":active — element is being clicked (mouse button held down). "
            ":nth-child(n) — the nth child of its parent. "
            ":nth-child(odd) / :nth-child(even) — stripes (great for tables). "
            ":first-child / :last-child — first or last child of parent. "
            ":checked — for checkboxes/radios that are checked. "
            "Pseudo-classes can be chained: li:nth-child(odd):hover."
        ),
        "try_changes": [
            ("Change :nth-child(odd) to :nth-child(even)", "stripes flip"),
            ("Add li:nth-child(3) { background: #f85149; color: white; }", "third item becomes red"),
            ("Change :hover to :active", "color only changes WHILE clicking"),
            ("Change li:first-child border-left color from #58a6ff to #f85149", "first item's accent becomes red"),
        ],
    },
    {
        "slug": "css-responsive-media-queries",
        "category": "CSS",
        "title": "@media — responsive design",
        "language": "css",
        "summary": "@media (max-width: 600px) applies styles only on small screens. Resize your browser to see.",
        "starter_code": ".card {\n  background: #a0c000;\n  color: white;\n  padding: 20px;\n  border-radius: 8px;\n  font-size: 18px;\n}\n\n@media (max-width: 600px) {\n  .card {\n    background: #f85149;\n    font-size: 14px;\n    padding: 10px;\n  }\n}",
        "html_template": "<div class=\"card\">Resize your browser window narrow and wide.<br>This card changes color and size at 600px breakpoint.</div>",
        "explanation": (
            "@media (condition) { ... } applies the styles inside only when the condition is true. "
            "(max-width: 600px) — viewport is 600px wide or less (phones). "
            "(min-width: 768px) — viewport is 768px or wider (tablets/desktops). "
            "(orientation: portrait) — device is in portrait mode. "
            "Mobile-first approach: write base styles for mobile, then add @media (min-width: 768px) for desktop. "
            "Common breakpoints: 480px (phone), 768px (tablet), 1024px (laptop), 1280px (desktop)."
        ),
        "try_changes": [
            ("Change max-width: 600px to max-width: 400px", "red color only shows on very narrow screens"),
            ("Change max-width: 600px to min-width: 600px", "red color shows on WIDE screens (opposite)"),
            ("Add a second @media (max-width: 400px) block with font-size: 10px", "third size kicks in on phones"),
        ],
    },
    {
        "slug": "css-cascade-specificity",
        "category": "CSS",
        "title": "Cascade + specificity — which rule wins?",
        "language": "css",
        "summary": "When multiple rules target the same element, the browser picks the winner by specificity. IDs beat classes, classes beat tags.",
        "starter_code": "/* specificity: 0,0,1 (one tag) */\ndiv { color: blue; }\n\n/* specificity: 0,1,0 (one class) — wins over tag */\n.card { color: green; }\n\n/* specificity: 1,0,0 (one ID) — wins over class */\n#special { color: red; }\n\n/* inline style wins over everything except !important */\n/* <div style=\"color: purple\"> */\n\n/* !important wins over EVERYTHING */\n.override { color: orange !important; }",
        "html_template": "<div class=\"card\">I'm green (class beats tag)</div>\n<div class=\"card\" id=\"special\">I'm red (ID beats class)</div>\n<div class=\"card override\">I'm orange (!important beats everything)</div>\n<div class=\"card\" style=\"color: purple;\">I'm purple (inline beats class)</div>",
        "explanation": (
            "Specificity is a 3-number score: (IDs, classes, tags). "
            "  div = (0, 0, 1) = 1 point. "
            "  .card = (0, 1, 0) = 10 points. "
            "  #special = (1, 0, 0) = 100 points. "
            "  div.card.box = (0, 2, 1) = 21 points. "
            "Higher specificity wins. Ties go to the LAST rule defined. "
            "Inline style (style='...') beats all selectors. "
            "!important beats everything — use it sparingly (it's a smell). "
            "Order of resolution: !important > inline > ID > class > tag > * (universal)."
        ),
        "try_changes": [
            ("Change .card to div.card (adds a tag, doesn't change specificity)", "still green — specificity unchanged"),
            ("Change .card to .card.card (doubles the class)", "now (0, 2, 0) — beats single .card, ties with ID? No, ID still wins"),
            ("Remove !important from .override", "orange loses to inline style=\"purple\""),
            ("Add !important to #special", "red beats orange — ID !important wins"),
        ],
    },

    # ─── CSS labs for building REAL webpages ─────────────────────────
    # These labs cover the full patterns a data scientist needs to build
    # a dashboard: reset, variables, page layout, navbar, sidebar,
    # dashboard grid, forms, tables, alerts, modal, loading, badges,
    # chart containers, footer, tabs.

    {
        "slug": "css-reset",
        "category": "CSS",
        "title": "CSS Reset — start every project with this",
        "language": "css",
        "summary": "Remove default browser margins, set box-sizing: border-box on everything. The FIRST 4 lines of every CSS file.",
        "starter_code": "/* RESET — remove all default margins/padding */\n* {\n  margin: 0;\n  padding: 0;\n  box-sizing: border-box;\n}\n\n/* Base font + colors */\nbody {\n  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;\n  font-size: 16px;\n  line-height: 1.6;\n  color: #1a1a1a;\n  background: #f5f5f5;\n}\n\n/* Headings inherit line-height */\nh1, h2, h3, h4, h5, h6 {\n  line-height: 1.3;\n  margin-bottom: 0.5rem;\n}\n\n/* Links */\na {\n  color: #a0c000;\n  text-decoration: none;\n}\na:hover {\n  text-decoration: underline;\n}\n\n/* Lists — remove bullets by default */\nul, ol {\n  list-style: none;\n}",
        "html_template": "<h1>Page Title</h1>\n<p>This page uses the CSS reset on the left. Without the reset, the browser\nadds default margins to h1, p, ul, etc. — making every project look\nslightly different.</p>\n<h2>Why reset?</h2>\n<ul>\n  <li>Consistent starting point across browsers</li>\n  <li>No surprise margins or paddings</li>\n  <li>box-sizing: border-box makes layouts predictable</li>\n</ul>\n<a href=\"#\">This is a link</a>",
        "explanation": (
            "* { margin: 0; padding: 0; box-sizing: border-box; } is the most important line in CSS. "
            "It removes ALL default browser margins/paddings (which differ between Chrome, Firefox, Safari) "
            "and sets box-sizing: border-box so padding doesn't add to the element's width. "
            "Without border-box: a 200px box with 20px padding is actually 240px wide — breaks layouts. "
            "With border-box: 200px stays 200px, padding eats into the content area. "
            "Set a base font-family + size on body — everything inherits it. "
            "Remove list bullets (list-style: none) — you'll add them back selectively where needed."
        ),
        "try_changes": [
            ("Comment out the * { } block (wrap it in /* */)", "all the default margins come back — h1 gets a big top margin, ul gets bullets"),
            ("Change font-size: 16px to 14px", "all text shrinks (inherited from body)"),
            ("Change color: #1a1a1a to #666", "all text becomes grey (inherited)"),
            ("Add list-style: disc; to the ul, ol rule", "bullets come back"),
        ],
    },
    {
        "slug": "css-variables",
        "category": "CSS",
        "title": "CSS Variables (custom properties) — :root",
        "language": "css",
        "summary": "Define colors/sizes once in :root, use var(--name) everywhere. Change once, updates everywhere.",
        "starter_code": ":root {\n  /* Colors */\n  --color-primary: #a0c000;\n  --color-secondary: #58a6ff;\n  --color-danger: #f85149;\n  --color-bg: #f5f5f5;\n  --color-text: #1a1a1a;\n  --color-text-muted: #666;\n  --color-border: #ddd;\n\n  /* Spacing */\n  --space-sm: 0.5rem;\n  --space-md: 1rem;\n  --space-lg: 2rem;\n\n  /* Radius */\n  --radius: 8px;\n}\n\nbody {\n  background: var(--color-bg);\n  color: var(--color-text);\n  font-family: sans-serif;\n  padding: var(--space-lg);\n}\n\n.card {\n  background: white;\n  border: 1px solid var(--color-border);\n  border-radius: var(--radius);\n  padding: var(--space-lg);\n  margin-bottom: var(--space-md);\n}\n\n.btn {\n  background: var(--color-primary);\n  color: white;\n  border: none;\n  padding: var(--space-sm) var(--space-md);\n  border-radius: var(--radius);\n  cursor: pointer;\n}\n\n.alert-danger {\n  background: var(--color-danger);\n  color: white;\n  padding: var(--space-md);\n  border-radius: var(--radius);\n}",
        "html_template": "<div class=\"card\">\n  <h3>My Card</h3>\n  <p>This card uses var(--color-border) for its border and var(--space-lg) for padding.</p>\n  <button class=\"btn\">Primary Button</button>\n</div>\n<div class=\"alert-danger\">\n  Something went wrong!\n</div>",
        "explanation": (
            ":root is the highest-level selector — it targets <html>. Variables defined here are available everywhere. "
            "Define variables with --name: value; Use them with var(--name). "
            "Benefits: (1) change a color in ONE place, it updates across the whole site. "
            "(2) Consistent spacing — every padding/margin uses --space-sm/md/lg. "
            "(3) Easy theming — override variables in a @media query or a .dark-mode class to switch the whole palette. "
            "Variables can reference other variables: --color-primary-light: color-mix(in srgb, var(--color-primary) 30%, white). "
            "Fallback values: var(--color-primary, #ccc) — uses #ccc if --color-primary isn't defined."
        ),
        "try_changes": [
            ("Change --color-primary from #a0c000 to #58a6ff", "button + any var(--color-primary) element changes to blue"),
            ("Change --space-lg from 2rem to 4rem", "all large spacing doubles — card padding grows"),
            ("Change --radius from 8px to 20px", "all rounded corners become more rounded"),
            ("Add --color-primary: #f85149 inside a .card { } rule", "only .card gets the overridden color (scoped variable)"),
        ],
    },
    {
        "slug": "css-page-layout",
        "category": "CSS",
        "title": "Full page layout — header + sidebar + main + footer",
        "language": "css",
        "summary": "The classic dashboard layout: fixed header on top, sidebar on left, main content fills the rest, footer at bottom.",
        "starter_code": "* { margin: 0; padding: 0; box-sizing: border-box; }\n\nbody {\n  font-family: sans-serif;\n  display: grid;\n  grid-template-areas:\n    \"header header\"\n    \"sidebar main\"\n    \"footer footer\";\n  grid-template-columns: 200px 1fr;\n  grid-template-rows: auto 1fr auto;\n  min-height: 100vh;\n}\n\n.header {\n  grid-area: header;\n  background: #1a1a1a;\n  color: white;\n  padding: 1rem 1.5rem;\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n}\n\n.sidebar {\n  grid-area: sidebar;\n  background: #2a2a2a;\n  color: #ccc;\n  padding: 1rem;\n}\n\n.sidebar a {\n  display: block;\n  color: #ccc;\n  padding: 0.5rem;\n  border-radius: 4px;\n  text-decoration: none;\n}\n.sidebar a:hover { background: #3a3a3a; color: white; }\n\n.main {\n  grid-area: main;\n  background: #f5f5f5;\n  padding: 1.5rem;\n}\n\n.footer {\n  grid-area: footer;\n  background: #1a1a1a;\n  color: #888;\n  padding: 1rem;\n  text-align: center;\n  font-size: 0.85rem;\n}",
        "html_template": "<div class=\"header\">\n  <h2>My Dashboard</h2>\n  <span>Welcome, User</span>\n</div>\n<aside class=\"sidebar\">\n  <a href=\"#\">Dashboard</a>\n  <a href=\"#\">Models</a>\n  <a href=\"#\">Datasets</a>\n  <a href=\"#\">Settings</a>\n</aside>\n<main class=\"main\">\n  <h1>Welcome to your dashboard</h1>\n  <p>This is the main content area. It fills the remaining space between\n  the sidebar and the footer.</p>\n</main>\n<div class=\"footer\">\n  &copy; 2024 My App. All rights reserved.\n</div>",
        "explanation": (
            "CSS Grid is the best tool for full-page layout. "
            "grid-template-areas gives each section a NAME, then you assign elements to areas. "
            "  'header header' — header spans 2 columns. "
            "  'sidebar main' — sidebar left, main right. "
            "  'footer footer' — footer spans 2 columns. "
            "grid-template-columns: 200px 1fr — sidebar is fixed 200px, main takes the rest (1fr = 1 fraction). "
            "grid-template-rows: auto 1fr auto — header/footer size to content, main fills the remaining height. "
            "min-height: 100vh — body is at least the full viewport height, so the footer stays at the bottom even on short pages. "
            "This pattern: header/sidebar/main/footer is the skeleton of almost every web app."
        ),
        "try_changes": [
            ("Change grid-template-columns: 200px 1fr to 250px 1fr", "sidebar becomes wider"),
            ("Change 200px to 0 (and set sidebar to display: none)", "sidebar disappears — main takes full width"),
            ("Change the grid-template-areas to put sidebar on the right:\n    \"header header\"\n    \"main sidebar\"\n    \"footer footer\"", "sidebar moves to the right side"),
            ("Change min-height: 100vh to min-height: 200vh", "page becomes very tall — you can scroll"),
        ],
    },
    {
        "slug": "css-navbar",
        "category": "CSS",
        "title": "Navbar — horizontal navigation bar",
        "language": "css",
        "summary": "Logo on the left, links on the right. Sticky at the top. The most common UI element.",
        "starter_code": ".navbar {\n  background: #1a1a1a;\n  padding: 0 1.5rem;\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n  position: sticky;\n  top: 0;\n  z-index: 100;\n  box-shadow: 0 2px 8px rgba(0,0,0,0.15);\n}\n\n.navbar .logo {\n  color: #a0c000;\n  font-size: 1.3rem;\n  font-weight: 700;\n  text-decoration: none;\n}\n\n.navbar ul {\n  display: flex;\n  gap: 0.5rem;\n  list-style: none;\n}\n\n.navbar ul li a {\n  color: #ccc;\n  text-decoration: none;\n  padding: 0.8rem 1rem;\n  border-radius: 4px;\n  transition: all 0.15s;\n  display: block;\n}\n\n.navbar ul li a:hover {\n  color: white;\n  background: rgba(255,255,255,0.1);\n}\n\n.navbar ul li a.active {\n  color: #a0c000;\n  background: rgba(160,192,0,0.15);\n}",
        "html_template": "<nav class=\"navbar\">\n  <a href=\"#\" class=\"logo\">MyApp</a>\n  <ul>\n    <li><a href=\"#\" class=\"active\">Home</a></li>\n    <li><a href=\"#\">Models</a></li>\n    <li><a href=\"#\">Datasets</a></li>\n    <li><a href=\"#\">About</a></li>\n  </ul>\n</nav>\n<div style=\"padding: 2rem;\">\n  <p>Scroll down — the navbar sticks to the top.</p>\n  <p style=\"margin-top: 50vh;\">You scrolled!</p>\n</div>",
        "explanation": (
            "display: flex + justify-content: space-between pushes logo left, links right. "
            "position: sticky + top: 0 — the navbar stays at the top when you scroll. Unlike fixed, it takes up space in the flow. "
            "z-index: 100 — navbar stays above other content. "
            "The ul is also a flex container (display: flex) so the li items sit in a row. "
            "gap: 0.5rem — space between links (modern alternative to margin-right on each li). "
            "transition: all 0.15s on the links — hover color/background fades in smoothly. "
            "active class — marks the current page. Use it in your templates: <a class=\"active\">Home</a>."
        ),
        "try_changes": [
            ("Change position: sticky to position: fixed", "navbar floats over content — content slides under it (need padding-top on body)"),
            ("Change justify-content: space-between to center", "logo and links center together"),
            ("Change background: #1a1a1a to #a0c000", "navbar becomes green"),
            ("Change .navbar ul li a padding to 0.8rem 2rem", "links become wider"),
            ("Remove the box-shadow", "navbar loses its depth separator"),
        ],
    },
    {
        "slug": "css-card-grid",
        "category": "CSS",
        "title": "Responsive card grid — auto-fit",
        "language": "css",
        "summary": "Grid that automatically shows 1/2/3/4 columns based on screen width. No media queries needed!",
        "starter_code": ".card-grid {\n  display: grid;\n  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));\n  gap: 1rem;\n  padding: 1.5rem;\n}\n\n.card {\n  background: white;\n  border: 1px solid #ddd;\n  border-radius: 10px;\n  padding: 1.5rem;\n  transition: all 0.2s;\n}\n\n.card:hover {\n  transform: translateY(-3px);\n  box-shadow: 0 8px 20px rgba(0,0,0,0.1);\n}\n\n.card h3 {\n  color: #a0c000;\n  margin-bottom: 0.5rem;\n}\n\n.card .metric {\n  font-size: 2rem;\n  font-weight: 700;\n  color: #1a1a1a;\n}\n\n.card .label {\n  color: #666;\n  font-size: 0.85rem;\n}",
        "html_template": "<div class=\"card-grid\">\n  <div class=\"card\">\n    <h3>Accuracy</h3>\n    <div class=\"metric\">94.2%</div>\n    <div class=\"label\">+2.1% from last week</div>\n  </div>\n  <div class=\"card\">\n    <h3>Precision</h3>\n    <div class=\"metric\">91.8%</div>\n    <div class=\"label\">+0.5% from last week</div>\n  </div>\n  <div class=\"card\">\n    <h3>Recall</h3>\n    <div class=\"metric\">89.3%</div>\n    <div class=\"label\">-1.2% from last week</div>\n  </div>\n  <div class=\"card\">\n    <h3>F1 Score</h3>\n    <div class=\"metric\">90.5%</div>\n    <div class=\"label\">+0.3% from last week</div>\n  </div>\n  <div class=\"card\">\n    <h3>Latency</h3>\n    <div class=\"metric\">42ms</div>\n    <div class=\"label\">-8ms from last week</div>\n  </div>\n</div>",
        "explanation": (
            "repeat(auto-fit, minmax(250px, 1fr)) is the magic line. "
            "  auto-fit — create as many columns as fit in the container. "
            "  minmax(250px, 1fr) — each column is at least 250px, but can grow to fill space. "
            "Result: on a 1000px screen → 4 columns. On a 700px screen → 2 columns. On a 400px screen → 1 column. "
            "ALL WITHOUT MEDIA QUERIES. This is the #1 CSS trick for responsive dashboards. "
            "The cards show ML metrics — exactly what a data scientist needs. "
            "hover: translateY(-3px) + box-shadow — the card 'lifts' on hover, a common micro-interaction."
        ),
        "try_changes": [
            ("Change minmax(250px, 1fr) to minmax(150px, 1fr)", "more columns — cards are narrower"),
            ("Change minmax(250px, 1fr) to minmax(400px, 1fr)", "fewer columns — cards are wider"),
            ("Change gap: 1rem to gap: 2rem", "more space between cards"),
            ("Change translateY(-3px) to scale(1.05)", "card grows instead of lifting"),
            ("Change the .card h3 color to #58a6ff", "metric titles become blue"),
        ],
    },
    {
        "slug": "css-form-styling",
        "category": "CSS",
        "title": "Form styling — inputs, labels, focus, validation",
        "language": "css",
        "summary": "Make forms look professional: full-width inputs, clear labels, focus rings, error states.",
        "starter_code": ".form-group {\n  margin-bottom: 1.2rem;\n}\n\n.form-group label {\n  display: block;\n  font-size: 0.88rem;\n  font-weight: 600;\n  color: #333;\n  margin-bottom: 0.4rem;\n}\n\n.form-group input,\n.form-group select,\n.form-group textarea {\n  width: 100%;\n  padding: 0.6rem 0.8rem;\n  border: 2px solid #ddd;\n  border-radius: 6px;\n  font-size: 0.95rem;\n  font-family: inherit;\n  transition: border-color 0.15s, box-shadow 0.15s;\n  outline: none;\n}\n\n.form-group input:focus {\n  border-color: #a0c000;\n  box-shadow: 0 0 0 3px rgba(160,192,0,0.2);\n}\n\n.form-group input:invalid:not(:placeholder-shown) {\n  border-color: #f85149;\n}\n\n.form-group .hint {\n  font-size: 0.8rem;\n  color: #666;\n  margin-top: 0.3rem;\n}\n\n.btn-submit {\n  background: #a0c000;\n  color: white;\n  border: none;\n  padding: 0.8rem 2rem;\n  border-radius: 6px;\n  font-size: 1rem;\n  font-weight: 600;\n  cursor: pointer;\n  transition: background 0.15s;\n}\n\n.btn-submit:hover {\n  background: #8aab00;\n}\n\n.btn-submit:active {\n  transform: scale(0.98);\n}",
        "html_template": "<form style=\"max-width: 400px; margin: 2rem auto;\">\n  <div class=\"form-group\">\n    <label for=\"name\">Model Name</label>\n    <input type=\"text\" id=\"name\" placeholder=\"My RandomForest\" required>\n    <div class=\"hint\">Give your model a descriptive name.</div>\n  </div>\n  <div class=\"form-group\">\n    <label for=\"email\">Email</label>\n    <input type=\"email\" id=\"email\" placeholder=\"you@example.com\" required>\n  </div>\n  <div class=\"form-group\">\n    <label for=\"age\">Max Depth</label>\n    <input type=\"number\" id=\"age\" value=\"10\" min=\"1\" max=\"50\">\n  </div>\n  <button type=\"submit\" class=\"btn-submit\">Train Model</button>\n</form>",
        "explanation": (
            "display: block on labels — puts label above input (not next to it). "
            "width: 100% on inputs — full width of the form-group. "
            "font-family: inherit — inputs don't inherit body font by default; this fixes it. "
            "outline: none + :focus styles — replace the ugly browser default focus ring with a branded one. "
            "box-shadow: 0 0 0 3px rgba(...) — the 'glow' around a focused input. Called a 'focus ring'. "
            ":invalid:not(:placeholder-shown) — shows red border ONLY after the user types something invalid. "
            "  Without :not(:placeholder-shown), the input would be red from the start (before typing). "
            ":active { transform: scale(0.98) } — button 'presses down' when clicked. Micro-interaction."
        ),
        "try_changes": [
            ("Change border: 2px solid #ddd to 1px solid #ccc", "thinner, lighter border"),
            ("Change the focus box-shadow spread from 3px to 5px", "thicker focus ring"),
            ("Change :invalid border-color from #f85149 to #ffa657", "invalid inputs get orange border (warning instead of error)"),
            ("Change .btn-submit background to #f85149", "submit button becomes red (danger button)"),
            ("Add 'disabled' attribute to the submit button and style .btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }", "button looks disabled"),
        ],
    },
    {
        "slug": "css-table-styling",
        "category": "CSS",
        "title": "Data table — striped rows, hover, sortable header",
        "language": "css",
        "summary": "The table style every dashboard needs: striped rows, hover highlight, bold header, right-aligned numbers.",
        "starter_code": ".data-table {\n  width: 100%;\n  border-collapse: collapse;\n  font-size: 0.9rem;\n  background: white;\n  border-radius: 8px;\n  overflow: hidden;\n  box-shadow: 0 1px 3px rgba(0,0,0,0.08);\n}\n\n.data-table thead {\n  background: #1a1a1a;\n  color: white;\n}\n\n.data-table th {\n  padding: 0.8rem 1rem;\n  text-align: left;\n  font-weight: 600;\n  font-size: 0.82rem;\n  text-transform: uppercase;\n  letter-spacing: 0.5px;\n}\n\n.data-table td {\n  padding: 0.7rem 1rem;\n  border-bottom: 1px solid #eee;\n}\n\n/* Zebra stripes */\n.data-table tbody tr:nth-child(even) {\n  background: #f9f9f9;\n}\n\n/* Hover highlight */\n.data-table tbody tr:hover {\n  background: rgba(160,192,0,0.08);\n}\n\n/* Right-align numeric columns */\n.data-table td.num {\n  text-align: right;\n  font-family: monospace;\n}\n\n/* Status badge cell */\n.data-table td .badge {\n  display: inline-block;\n  padding: 0.2rem 0.6rem;\n  border-radius: 999px;\n  font-size: 0.78rem;\n  font-weight: 600;\n}\n.badge.success { background: #3fb95022; color: #3fb950; }\n.badge.fail    { background: #f8514922; color: #f85149; }",
        "html_template": "<table class=\"data-table\">\n  <thead>\n    <tr>\n      <th>Model</th>\n      <th>Dataset</th>\n      <th class=\"num\">Accuracy</th>\n      <th class=\"num\">Latency</th>\n      <th>Status</th>\n    </tr>\n  </thead>\n  <tbody>\n    <tr>\n      <td>RandomForest</td><td>Iris</td><td class=\"num\">0.942</td><td class=\"num\">12ms</td>\n      <td><span class=\"badge success\">Trained</span></td>\n    </tr>\n    <tr>\n      <td>XGBoost</td><td>Iris</td><td class=\"num\">0.951</td><td class=\"num\">8ms</td>\n      <td><span class=\"badge success\">Trained</span></td>\n    </tr>\n    <tr>\n      <td>NeuralNet</td><td>Iris</td><td class=\"num\">0.938</td><td class=\"num\">45ms</td>\n      <td><span class=\"badge fail\">Failed</span></td>\n    </tr>\n    <tr>\n      <td>LogReg</td><td>Iris</td><td class=\"num\">0.893</td><td class=\"num\">3ms</td>\n      <td><span class=\"badge success\">Trained</span></td>\n    </tr>\n  </tbody>\n</table>",
        "explanation": (
            "border-collapse: collapse — removes the double-border between cells. Always use this for tables. "
            "overflow: hidden + border-radius — clips the header's background to the rounded corners. "
            "thead has a dark background, tbody is white — classic dashboard look. "
            "nth-child(even) — zebra stripes. Improves readability on wide tables. "
            "tr:hover — highlights the row the mouse is over. Helps users track across wide rows. "
            "td.num { text-align: right; font-family: monospace } — right-aligned monospace numbers are easier to compare. "
            "Badges (success/fail) use semi-transparent background + solid text color — looks modern without being heavy."
        ),
        "try_changes": [
            ("Change nth-child(even) to nth-child(odd)", "stripes flip — odd rows get the background"),
            ("Change the thead background from #1a1a1a to #a0c000", "header becomes green"),
            ("Change the hover background from rgba(160,192,0,0.08) to rgba(88,166,255,0.1)", "hover becomes blue"),
            ("Add .data-table td:first-child { font-weight: 600; }", "first column (model name) becomes bold"),
            ("Change text-transform: uppercase to none", "header text becomes normal case"),
        ],
    },
    {
        "slug": "css-alerts",
        "category": "CSS",
        "title": "Alert boxes — success, error, warning, info",
        "language": "css",
        "summary": "4 colored boxes for user feedback. Each has an icon, a title, and a message.",
        "starter_code": ".alert {\n  padding: 1rem 1.2rem;\n  border-radius: 8px;\n  margin-bottom: 1rem;\n  display: flex;\n  align-items: flex-start;\n  gap: 0.8rem;\n  border-left: 4px solid;\n}\n\n.alert .icon {\n  font-size: 1.3rem;\n  line-height: 1;\n}\n\n.alert .content {\n  flex: 1;\n}\n\n.alert .title {\n  font-weight: 700;\n  margin-bottom: 0.2rem;\n}\n\n.alert .msg {\n  font-size: 0.88rem;\n  opacity: 0.9;\n}\n\n/* Success — green */\n.alert-success {\n  background: #3fb95015;\n  border-left-color: #3fb950;\n  color: #1a5e1a;\n}\n\n/* Error — red */\n.alert-error {\n  background: #f8514915;\n  border-left-color: #f85149;\n  color: #8b1a1a;\n}\n\n/* Warning — orange */\n.alert-warning {\n  background: #ffa65715;\n  border-left-color: #ffa657;\n  color: #8b5a1a;\n}\n\n/* Info — blue */\n.alert-info {\n  background: #58a6ff15;\n  border-left-color: #58a6ff;\n  color: #1a4a8b;\n}",
        "html_template": "<div class=\"alert alert-success\">\n  <span class=\"icon\">&#10003;</span>\n  <div class=\"content\">\n    <div class=\"title\">Model trained successfully</div>\n    <div class=\"msg\">RandomForest reached 94.2% accuracy on the test set.</div>\n  </div>\n</div>\n\n<div class=\"alert alert-error\">\n  <span class=\"icon\">&#10007;</span>\n  <div class=\"content\">\n    <div class=\"title\">Training failed</div>\n    <div class=\"msg\">CUDA out of memory. Try reducing batch size.</div>\n  </div>\n</div>\n\n<div class=\"alert alert-warning\">\n  <span class=\"icon\">&#9888;</span>\n  <div class=\"content\">\n    <div class=\"title\">Deprecated feature</div>\n    <div class=\"msg\">model.fit() will be removed in v2.0. Use model.train() instead.</div>\n  </div>\n</div>\n\n<div class=\"alert alert-info\">\n  <span class=\"icon\">&#8505;</span>\n  <div class=\"content\">\n    <div class=\"title\">Tip</div>\n    <div class=\"msg\">You can speed up training by enabling GPU acceleration in Settings.</div>\n  </div>\n</div>",
        "explanation": (
            "Every alert has the same STRUCTURE (icon + title + msg) but different COLORS. "
            "The base .alert class handles layout (flex, gap, padding, border-left). "
            "The .alert-success/error/warning/info classes only set colors. "
            "border-left: 4px solid — a colored bar on the left. The actual color is set per-type. "
            "Background uses hex + '15' suffix = 8% opacity (hex alpha: 15 = 0x15 = 21/255 ≈ 8%). "
            "Text color is a DARKER shade of the same hue — keeps it readable on the light background. "
            "display: flex + align-items: flex-start — icon sits at the top-left, content fills the rest."
        ),
        "try_changes": [
            ("Change border-left: 4px to 8px", "thicker colored bar on the left"),
            ("Change .alert-success background to #3fb95030", "darker green background (more opaque)"),
            ("Add a 5th type: .alert-neutral { background: #88888815; border-left-color: #888; color: #333; }", "grey neutral alert"),
            ("Change border-radius: 8px to 0", "sharp corners — more 'system message' look"),
        ],
    },
    {
        "slug": "css-loading-spinner",
        "category": "CSS",
        "title": "Loading spinner — pure CSS animation",
        "language": "css",
        "summary": "A spinning circle that shows 'loading in progress'. No JavaScript, no images — pure CSS.",
        "starter_code": ".spinner {\n  width: 40px;\n  height: 40px;\n  border: 4px solid #e0e0e0;\n  border-top-color: #a0c000;\n  border-radius: 50%;\n  animation: spin 0.8s linear infinite;\n}\n\n@keyframes spin {\n  to { transform: rotate(360deg); }\n}\n\n/* Loading container — centers the spinner + text */\n.loading {\n  display: flex;\n  flex-direction: column;\n  align-items: center;\n  gap: 1rem;\n  padding: 3rem;\n}\n\n.loading .text {\n  color: #666;\n  font-size: 0.9rem;\n}\n\n/* Skeleton loader — for content that's loading */\n.skeleton {\n  background: linear-gradient(90deg, #eee 25%, #f5f5f5 50%, #eee 75%);\n  background-size: 200% 100%;\n  animation: shimmer 1.5s infinite;\n  border-radius: 4px;\n  height: 1rem;\n  margin-bottom: 0.5rem;\n}\n\n@keyframes shimmer {\n  0%   { background-position: 200% 0; }\n  100% { background-position: -200% 0; }\n}",
        "html_template": "<div class=\"loading\">\n  <div class=\"spinner\"></div>\n  <div class=\"text\">Training model... 42%</div>\n</div>\n\n<div style=\"padding: 2rem;\">\n  <h3>Skeleton loader (content loading):</h3>\n  <div class=\"skeleton\" style=\"width: 60%;\"></div>\n  <div class=\"skeleton\" style=\"width: 80%;\"></div>\n  <div class=\"skeleton\" style=\"width: 70%;\"></div>\n  <div class=\"skeleton\" style=\"width: 50%;\"></div>\n</div>",
        "explanation": (
            "The spinner is a circle (border-radius: 50%) with a colored top border. "
            "animation: spin 0.8s linear infinite — rotates 360 degrees every 0.8 seconds, forever. "
            "@keyframes spin defines the animation: 'to { transform: rotate(360deg) }' means 'end at 360 degrees'. "
            "linear — constant speed (ease would speed up/slow down, which looks wrong for a spinner). "
            "The skeleton loader uses a moving gradient — gives the illusion of content loading. "
            "background-size: 200% 100% — gradient is 2x the element width, so it can slide. "
            "background-position animates from 200% to -200% — the gradient slides left, creating a 'shimmer'."
        ),
        "try_changes": [
            ("Change the spinner border-top-color to #f85149", "spinner becomes red"),
            ("Change animation duration from 0.8s to 2s", "spinner rotates much slower"),
            ("Change linear to ease-in-out", "spinner speeds up and slows down (feels organic)"),
            ("Change the spinner width/height from 40px to 60px", "bigger spinner"),
            ("Change the skeleton animation from 1.5s to 0.5s", "shimmer moves faster"),
        ],
    },
    {
        "slug": "css-chart-container",
        "category": "CSS",
        "title": "Chart container — figure + caption for plots",
        "language": "css",
        "summary": "A styled wrapper for matplotlib/plotly charts. White card, title, the chart, and a caption.",
        "starter_code": ".chart-card {\n  background: white;\n  border: 1px solid #e0e0e0;\n  border-radius: 10px;\n  padding: 1.5rem;\n  margin-bottom: 1.5rem;\n  box-shadow: 0 1px 3px rgba(0,0,0,0.06);\n}\n\n.chart-card .chart-header {\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n  margin-bottom: 1rem;\n}\n\n.chart-card .chart-title {\n  font-size: 1.05rem;\n  font-weight: 600;\n  color: #1a1a1a;\n  margin: 0;\n}\n\n.chart-card .chart-subtitle {\n  font-size: 0.82rem;\n  color: #666;\n  margin-top: 0.2rem;\n}\n\n.chart-card .chart-actions {\n  display: flex;\n  gap: 0.4rem;\n}\n\n.chart-card .chart-actions button {\n  background: #f5f5f5;\n  border: 1px solid #ddd;\n  border-radius: 5px;\n  padding: 0.3rem 0.7rem;\n  font-size: 0.78rem;\n  color: #666;\n  cursor: pointer;\n  transition: all 0.15s;\n}\n\n.chart-card .chart-actions button:hover {\n  background: #a0c000;\n  color: white;\n  border-color: #a0c000;\n}\n\n.chart-card .chart-body {\n  width: 100%;\n  height: 300px;\n  background: #fafafa;\n  border-radius: 6px;\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  color: #999;\n  font-size: 0.9rem;\n}\n\n.chart-card .chart-caption {\n  font-size: 0.8rem;\n  color: #888;\n  margin-top: 0.8rem;\n  font-style: italic;\n}",
        "html_template": "<div class=\"chart-card\">\n  <div class=\"chart-header\">\n    <div>\n      <h3 class=\"chart-title\">Model Accuracy Over Time</h3>\n      <div class=\"chart-subtitle\">Last 30 days &middot; test set</div>\n    </div>\n    <div class=\"chart-actions\">\n      <button>Download</button>\n      <button>Fullscreen</button>\n    </div>\n  </div>\n  <div class=\"chart-body\">\n    [ Your matplotlib / plotly chart goes here ]\n  </div>\n  <div class=\"chart-caption\">\n    Figure 1: Accuracy improved 12% after hyperparameter tuning on day 15.\n  </div>\n</div>",
        "explanation": (
            "This is the wrapper pattern for EVERY chart in a data-science dashboard. "
            "chart-header — title + subtitle on the left, action buttons (download, fullscreen) on the right. "
            "chart-body — fixed height (300px) so all charts in a grid are the same size. "
            "  The actual chart (an <img> from matplotlib, or a <div> for plotly) goes inside. "
            "chart-caption — italic grey text below, like a figure caption in a paper. "
            "box-shadow: 0 1px 3px rgba(0,0,0,0.06) — very subtle shadow. Don't overdo shadows on cards. "
            "The action buttons are grey by default, turn green on hover — branded micro-interaction."
        ),
        "try_changes": [
            ("Change chart-body height from 300px to 500px", "taller chart area"),
            ("Change the button hover color from #a0c000 to #58a6ff", "buttons turn blue on hover"),
            ("Change border-radius: 10px to 0", "sharp corners — more 'academic paper' look"),
            ("Add a max-width: 800px to .chart-card", "chart doesn't stretch too wide on big screens"),
        ],
    },
    {
        "slug": "css-modal",
        "category": "CSS",
        "title": "Modal dialog — overlay + centered box",
        "language": "css",
        "summary": "A dialog that floats above the page. Dark overlay behind, centered white box, close button.",
        "starter_code": "/* The overlay — covers the whole page */\n.modal-overlay {\n  position: fixed;\n  top: 0; left: 0;\n  width: 100%; height: 100%;\n  background: rgba(0,0,0,0.5);\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  z-index: 1000;\n  backdrop-filter: blur(2px);\n}\n\n/* The modal box itself */\n.modal {\n  background: white;\n  border-radius: 12px;\n  padding: 0;\n  width: 90%;\n  max-width: 500px;\n  box-shadow: 0 20px 60px rgba(0,0,0,0.3);\n  animation: modalIn 0.2s ease-out;\n}\n\n@keyframes modalIn {\n  from { transform: scale(0.9); opacity: 0; }\n  to   { transform: scale(1);   opacity: 1; }\n}\n\n.modal .modal-header {\n  padding: 1.2rem 1.5rem;\n  border-bottom: 1px solid #eee;\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n}\n\n.modal .modal-header h3 {\n  margin: 0;\n  font-size: 1.1rem;\n}\n\n.modal .close-btn {\n  background: none;\n  border: none;\n  font-size: 1.5rem;\n  color: #999;\n  cursor: pointer;\n  padding: 0;\n  line-height: 1;\n}\n\n.modal .close-btn:hover { color: #333; }\n\n.modal .modal-body {\n  padding: 1.5rem;\n  color: #333;\n  line-height: 1.6;\n}\n\n.modal .modal-footer {\n  padding: 1rem 1.5rem;\n  border-top: 1px solid #eee;\n  display: flex;\n  gap: 0.5rem;\n  justify-content: flex-end;\n}\n\n.modal .btn-secondary {\n  background: #f5f5f5;\n  border: 1px solid #ddd;\n  border-radius: 6px;\n  padding: 0.5rem 1.2rem;\n  cursor: pointer;\n}\n\n.modal .btn-primary {\n  background: #a0c000;\n  color: white;\n  border: none;\n  border-radius: 6px;\n  padding: 0.5rem 1.2rem;\n  cursor: pointer;\n}",
        "html_template": "<div class=\"modal-overlay\">\n  <div class=\"modal\">\n    <div class=\"modal-header\">\n      <h3>Delete Model?</h3>\n      <button class=\"close-btn\">&times;</button>\n    </div>\n    <div class=\"modal-body\">\n      Are you sure you want to delete <strong>RandomForest_v2</strong>?\n      This action cannot be undone. All benchmark results for this model\n      will also be removed.\n    </div>\n    <div class=\"modal-footer\">\n      <button class=\"btn-secondary\">Cancel</button>\n      <button class=\"btn-primary\">Delete</button>\n    </div>\n  </div>\n</div>",
        "explanation": (
            "position: fixed + top: 0; width: 100%; height: 100% — the overlay covers the ENTIRE viewport. "
            "background: rgba(0,0,0,0.5) — semi-transparent black. Dims the page behind the modal. "
            "display: flex + align-items: center + justify-content: center — centers the modal box. "
            "z-index: 1000 — modal is above everything else on the page. "
            "backdrop-filter: blur(2px) — blurs the content behind the overlay (modern, supported in most browsers). "
            "max-width: 500px + width: 90% — responsive: 500px on desktop, 90% on mobile. "
            "@keyframes modalIn — the modal scales up from 0.9 to 1.0 with a fade-in. Feels smooth. "
            "Structure: header (title + close), body (content), footer (action buttons). Classic dialog pattern."
        ),
        "try_changes": [
            ("Change rgba(0,0,0,0.5) to rgba(0,0,0,0.8)", "darker overlay — more dramatic"),
            ("Change max-width: 500px to 800px", "wider modal"),
            ("Change the animation duration from 0.2s to 0.5s", "slower entrance"),
            ("Remove backdrop-filter: blur(2px)", "no blur behind the modal"),
            ("Change border-radius: 12px to 0", "sharp corners — more 'system dialog' look"),
        ],
    },
    {
        "slug": "css-badges-tags",
        "category": "CSS",
        "title": "Badges + tags — small status labels",
        "language": "css",
        "summary": "Pills, dots, and tags for status indicators. 'Trained', 'v2.1', 'GPU', 'beta' — small colored labels.",
        "starter_code": "/* Pill badge — rounded, colored background */\n.badge {\n  display: inline-block;\n  padding: 0.2rem 0.7rem;\n  border-radius: 999px;\n  font-size: 0.78rem;\n  font-weight: 600;\n  line-height: 1.4;\n}\n\n.badge-success { background: #3fb95022; color: #3fb950; }\n.badge-warning { background: #ffa65722; color: #ffa657; }\n.badge-danger  { background: #f8514922; color: #f85149; }\n.badge-info    { background: #58a6ff22; color: #58a6ff; }\n.badge-neutral { background: #88888822; color: #666; }\n\n/* Status dot — a small colored circle */\n.status-dot {\n  display: inline-block;\n  width: 8px;\n  height: 8px;\n  border-radius: 50%;\n  margin-right: 0.4rem;\n}\n.status-dot.online  { background: #3fb950; }\n.status-dot.offline { background: #f85149; }\n.status-dot.idle    { background: #ffa657; }\n\n/* Tag — square, outlined */\n.tag {\n  display: inline-block;\n  padding: 0.15rem 0.5rem;\n  border: 1px solid #ddd;\n  border-radius: 4px;\n  font-size: 0.78rem;\n  color: #555;\n  background: #fafafa;\n  margin-right: 0.3rem;\n}\n\n/* Version pill — monospace, grey */\n.version {\n  font-family: monospace;\n  font-size: 0.78rem;\n  background: #1a1a1a;\n  color: #a0c000;\n  padding: 0.15rem 0.5rem;\n  border-radius: 4px;\n}",
        "html_template": "<h3>Badges</h3>\n<span class=\"badge badge-success\">Trained</span>\n<span class=\"badge badge-warning\">Training</span>\n<span class=\"badge badge-danger\">Failed</span>\n<span class=\"badge badge-info\">Info</span>\n<span class=\"badge badge-neutral\">Draft</span>\n\n<h3 style=\"margin-top: 1.5rem;\">Status dots</h3>\n<p><span class=\"status-dot online\"></span> Server online</p>\n<p><span class=\"status-dot offline\"></span> Database offline</p>\n<p><span class=\"status-dot idle\"></span> Worker idle</p>\n\n<h3 style=\"margin-top: 1.5rem;\">Tags</h3>\n<span class=\"tag\">python</span>\n<span class=\"tag\">scikit-learn</span>\n<span class=\"tag\">classification</span>\n<span class=\"tag\">GPU</span>\n\n<h3 style=\"margin-top: 1.5rem;\">Version</h3>\n<span class=\"version\">v2.1.3</span>",
        "explanation": (
            "Three types of small labels, each for a different purpose: "
            "BADGE — rounded pill with colored background + text. Used for status (Trained/Failed/Training). "
            "  The background is a 22-alpha hex (≈13% opacity) of the same color as the text — soft, modern look. "
            "STATUS DOT — just a small colored circle. Used with text: '• Online'. Minimal space. "
            "TAG — outlined, square-ish. Used for categories/labels (python, GPU, classification). "
            "VERSION — monospace, dark background, green text. Looks like a code/version number. "
            "All use display: inline-block so they sit inline with text and respect padding."
        ),
        "try_changes": [
            ("Change badge border-radius from 999px to 4px", "badges become square-ish"),
            ("Add a new badge type: .badge-primary { background: #a0c00022; color: #a0c000; }", "green branded badge"),
            ("Change the status-dot size from 8px to 12px", "bigger dots"),
            ("Change the tag border to 2px dashed #a0c000", "tags become dashed green"),
            ("Change the version color from #a0c000 to #58a6ff", "version becomes blue"),
        ],
    },
    {
        "slug": "css-footer",
        "category": "CSS",
        "title": "Footer — bottom of the page",
        "language": "css",
        "summary": "Multi-column footer with links, social icons, and copyright. The pattern every website uses.",
        "starter_code": ".footer {\n  background: #1a1a1a;\n  color: #999;\n  padding: 3rem 1.5rem 1.5rem;\n  margin-top: 3rem;\n}\n\n.footer .footer-grid {\n  display: grid;\n  grid-template-columns: 2fr 1fr 1fr 1fr;\n  gap: 2rem;\n  max-width: 1000px;\n  margin: 0 auto;\n}\n\n.footer .footer-col h4 {\n  color: white;\n  font-size: 0.9rem;\n  text-transform: uppercase;\n  letter-spacing: 0.5px;\n  margin-bottom: 0.8rem;\n}\n\n.footer .footer-col ul {\n  list-style: none;\n  padding: 0;\n}\n\n.footer .footer-col ul li {\n  margin-bottom: 0.4rem;\n}\n\n.footer .footer-col ul li a {\n  color: #999;\n  text-decoration: none;\n  font-size: 0.88rem;\n  transition: color 0.15s;\n}\n\n.footer .footer-col ul li a:hover {\n  color: #a0c000;\n}\n\n.footer .footer-brand p {\n  font-size: 0.85rem;\n  line-height: 1.6;\n  margin-top: 0.5rem;\n}\n\n.footer .footer-bottom {\n  border-top: 1px solid #333;\n  margin-top: 2rem;\n  padding-top: 1.5rem;\n  text-align: center;\n  font-size: 0.82rem;\n  color: #666;\n}",
        "html_template": "<footer class=\"footer\">\n  <div class=\"footer-grid\">\n    <div class=\"footer-col footer-brand\">\n      <h4>OpenBenchML</h4>\n      <p>Benchmark, compare, and deploy ML models in the browser.\n      Open source. Built with FastAPI + Jinja2 + scikit-learn.</p>\n    </div>\n    <div class=\"footer-col\">\n      <h4>Product</h4>\n      <ul>\n        <li><a href=\"#\">Models</a></li>\n        <li><a href=\"#\">Datasets</a></li>\n        <li><a href=\"#\">Notebook</a></li>\n        <li><a href=\"#\">Leaderboard</a></li>\n      </ul>\n    </div>\n    <div class=\"footer-col\">\n      <h4>Learn</h4>\n      <ul>\n        <li><a href=\"#\">Concepts</a></li>\n        <li><a href=\"#\">Project Course</a></li>\n        <li><a href=\"#\">Labs</a></li>\n        <li><a href=\"#\">Docs</a></li>\n      </ul>\n    </div>\n    <div class=\"footer-col\">\n      <h4>Company</h4>\n      <ul>\n        <li><a href=\"#\">About</a></li>\n        <li><a href=\"#\">GitHub</a></li>\n        <li><a href=\"#\">Privacy</a></li>\n        <li><a href=\"#\">Terms</a></li>\n      </ul>\n    </div>\n  </div>\n  <div class=\"footer-bottom\">\n    &copy; 2024 OpenBenchML. All rights reserved. Built with &#10084; by the community.\n  </div>\n</footer>",
        "explanation": (
            "The footer has 4 columns: brand (wider, 2fr) + 3 link columns (1fr each). "
            "grid-template-columns: 2fr 1fr 1fr 1fr — the brand column is twice as wide. "
            "max-width: 1000px + margin: 0 auto — centers the footer content on wide screens. "
            "Dark background (#1a1a1a) + grey text (#999) — standard footer look. "
            "Links are grey, turn green on hover — branded micro-interaction. "
            "footer-bottom — separated by a top border, centered, smaller text. Holds the copyright. "
            "text-transform: uppercase + letter-spacing on h4 — makes the column headers look like labels."
        ),
        "try_changes": [
            ("Change grid-template-columns from 2fr 1fr 1fr 1fr to 1fr 1fr 1fr 1fr", "all columns equal width"),
            ("Change the footer background from #1a1a1a to #2a1a3a", "footer becomes dark purple"),
            ("Change the link hover color from #a0c000 to #58a6ff", "links turn blue on hover"),
            ("Add a 5th column: <div class=\"footer-col\"><h4>Social</h4>...</div>", "5-column footer"),
        ],
    },
    {
        "slug": "css-tabs",
        "category": "CSS",
        "title": "Tabs — switch between panels",
        "language": "css",
        "summary": "Tab navigation that switches content panels. Pure CSS using :target or radio inputs (no JS needed for basic tabs).",
        "starter_code": "/* Tab navigation */\n.tabs {\n  border-bottom: 2px solid #e0e0e0;\n  display: flex;\n  gap: 0.3rem;\n  margin-bottom: 1.5rem;\n}\n\n.tabs .tab {\n  padding: 0.7rem 1.2rem;\n  border: none;\n  background: none;\n  font-size: 0.92rem;\n  color: #666;\n  cursor: pointer;\n  border-bottom: 3px solid transparent;\n  margin-bottom: -2px;\n  transition: all 0.15s;\n  font-family: inherit;\n}\n\n.tabs .tab:hover {\n  color: #333;\n  background: #f5f5f5;\n}\n\n.tabs .tab.active {\n  color: #a0c000;\n  border-bottom-color: #a0c000;\n  font-weight: 600;\n}\n\n/* Tab content panels */\n.tab-panel {\n  display: none;\n  padding: 1rem 0;\n  line-height: 1.6;\n}\n\n.tab-panel.active {\n  display: block;\n}",
        "html_template": "<div class=\"tabs\">\n  <button class=\"tab active\" onclick=\"document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));this.classList.add('active');document.getElementById('p1').classList.add('active')\">Overview</button>\n  <button class=\"tab\" onclick=\"document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));this.classList.add('active');document.getElementById('p2').classList.add('active')\">Metrics</button>\n  <button class=\"tab\" onclick=\"document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));this.classList.add('active');document.getElementById('p3').classList.add('active')\">Code</button>\n</div>\n<div class=\"tab-panel active\" id=\"p1\">\n  <h3>Overview</h3>\n  <p>RandomForest classifier trained on the Iris dataset. 100 trees, max depth 10.</p>\n</div>\n<div class=\"tab-panel\" id=\"p2\">\n  <h3>Metrics</h3>\n  <p>Accuracy: 94.2% | Precision: 91.8% | Recall: 89.3% | F1: 90.5%</p>\n</div>\n<div class=\"tab-panel\" id=\"p3\">\n  <h3>Code</h3>\n  <p>from sklearn.ensemble import RandomForestClassifier</p>\n  <p>clf = RandomForestClassifier(n_estimators=100, max_depth=10)</p>\n  <p>clf.fit(X_train, y_train)</p>\n</div>",
        "explanation": (
            "The .tabs container has a bottom border — the 'tab bar'. "
            "Each .tab is a <button> with: transparent background, bottom border that's invisible until active. "
            "margin-bottom: -2px — the tab's bottom border overlaps the tab bar's border (so the active tab 'connects'). "
            "Active tab: colored bottom border + colored text + bold. "
            "Tab panels: display: none by default, display: block when .active. "
            "The onclick JS just toggles .active classes — the CSS handles the visual switching. "
            "In a real app, you'd use addEventListener instead of inline onclick, but the CSS is the same."
        ),
        "try_changes": [
            ("Change border-bottom: 3px to 5px on .tab.active", "thicker active indicator"),
            ("Change the active color from #a0c000 to #58a6ff", "tabs become blue"),
            ("Change .tab font-size from 0.92rem to 1.1rem", "bigger tab labels"),
            ("Add border-radius: 6px 6px 0 0 to .tab", "tabs get rounded top corners"),
        ],
    },
    {
        "slug": "css-dashboard-layout",
        "category": "CSS",
        "title": "Full dashboard layout — sidebar + KPIs + charts + table",
        "language": "css",
        "summary": "The complete data-science dashboard: sidebar nav, KPI row, 2-column charts, data table.",
        "starter_code": "* { margin: 0; padding: 0; box-sizing: border-box; }\n\nbody { font-family: sans-serif; background: #f5f5f5; }\n\n.dashboard {\n  display: grid;\n  grid-template-columns: 220px 1fr;\n  min-height: 100vh;\n}\n\n/* Sidebar */\n.sidebar {\n  background: #1a1a1a;\n  color: #999;\n  padding: 1.5rem 0;\n}\n.sidebar .logo {\n  color: #a0c000;\n  font-size: 1.2rem;\n  font-weight: 700;\n  padding: 0 1.5rem 1.5rem;\n}\n.sidebar a {\n  display: block;\n  color: #999;\n  text-decoration: none;\n  padding: 0.7rem 1.5rem;\n  transition: all 0.15s;\n}\n.sidebar a:hover, .sidebar a.active {\n  background: rgba(160,192,0,0.15);\n  color: #a0c000;\n  border-left: 3px solid #a0c000;\n}\n\n/* Main content */\n.main {\n  padding: 2rem;\n  overflow: auto;\n}\n\n.main h1 { font-size: 1.5rem; margin-bottom: 1.5rem; }\n\n/* KPI row */\n.kpi-row {\n  display: grid;\n  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));\n  gap: 1rem;\n  margin-bottom: 1.5rem;\n}\n.kpi {\n  background: white;\n  border-radius: 10px;\n  padding: 1.2rem;\n  border: 1px solid #e0e0e0;\n}\n.kpi .label { font-size: 0.82rem; color: #666; }\n.kpi .value { font-size: 1.8rem; font-weight: 700; margin: 0.3rem 0; }\n.kpi .change { font-size: 0.78rem; }\n.kpi .change.up { color: #3fb950; }\n.kpi .change.down { color: #f85149; }\n\n/* Charts grid */\n.charts-grid {\n  display: grid;\n  grid-template-columns: 1fr 1fr;\n  gap: 1rem;\n  margin-bottom: 1.5rem;\n}\n@media (max-width: 768px) {\n  .charts-grid { grid-template-columns: 1fr; }\n}\n.chart-card {\n  background: white;\n  border-radius: 10px;\n  padding: 1.2rem;\n  border: 1px solid #e0e0e0;\n}\n.chart-card h3 { font-size: 0.95rem; margin-bottom: 1rem; }\n.chart-card .chart-area {\n  height: 200px;\n  background: #fafafa;\n  border-radius: 6px;\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  color: #999;\n  font-size: 0.85rem;\n}",
        "html_template": "<div class=\"dashboard\">\n  <aside class=\"sidebar\">\n    <div class=\"logo\">&#9889; ML Dash</div>\n    <a href=\"#\" class=\"active\">Dashboard</a>\n    <a href=\"#\">Models</a>\n    <a href=\"#\">Datasets</a>\n    <a href=\"#\">Experiments</a>\n    <a href=\"#\">Settings</a>\n  </aside>\n  <main class=\"main\">\n    <h1>Dashboard</h1>\n    <div class=\"kpi-row\">\n      <div class=\"kpi\">\n        <div class=\"label\">Total Models</div>\n        <div class=\"value\">24</div>\n        <div class=\"change up\">&#9650; 3 new this week</div>\n      </div>\n      <div class=\"kpi\">\n        <div class=\"label\">Avg Accuracy</div>\n        <div class=\"value\">91.4%</div>\n        <div class=\"change up\">&#9650; 2.1%</div>\n      </div>\n      <div class=\"kpi\">\n        <div class=\"label\">Avg Latency</div>\n        <div class=\"value\">38ms</div>\n        <div class=\"change down\">&#9660; 12ms</div>\n      </div>\n      <div class=\"kpi\">\n        <div class=\"label\">Active Jobs</div>\n        <div class=\"value\">3</div>\n        <div class=\"change\">2 training, 1 queued</div>\n      </div>\n    </div>\n    <div class=\"charts-grid\">\n      <div class=\"chart-card\">\n        <h3>Accuracy Over Time</h3>\n        <div class=\"chart-area\">[ Line chart ]</div>\n      </div>\n      <div class=\"chart-card\">\n        <h3>Model Comparison</h3>\n        <div class=\"chart-area\">[ Bar chart ]</div>\n      </div>\n    </div>\n  </main>\n</div>",
        "explanation": (
            "This is the COMPLETE dashboard pattern a data scientist needs: "
            "Grid: 220px sidebar + 1fr main. min-height: 100vh so the sidebar goes full height. "
            "Sidebar links: padding-left 1.5rem, border-left appears on active/hover — clear navigation. "
            "KPI row: repeat(auto-fit, minmax(180px, 1fr)) — responsive! 4 on desktop, 2 on tablet, 1 on mobile. "
            "Each KPI: label (small grey) + value (big bold) + change (green up / red down). "
            "Charts grid: 2 columns on desktop, 1 column on mobile (@media query). "
            "chart-area has a fixed height (200px) — all charts in the grid are the same size. "
            "Every card has the same border + border-radius + padding — visual consistency."
        ),
        "try_changes": [
            ("Change grid-template-columns: 220px 1fr to 280px 1fr", "wider sidebar"),
            ("Change the KPI minmax from 180px to 250px", "fewer KPIs per row"),
            ("Change the charts-grid from 1fr 1fr to 1fr 1fr 1fr", "3 charts per row"),
            ("Change @media max-width: 768px to 1024px", "charts stack earlier (on tablets)"),
            ("Change the sidebar background to #0d1117", "sidebar becomes darker (GitHub-style)"),
        ],
    },
    {
        "slug": "css-responsive-form-page",
        "category": "CSS",
        "title": "Responsive form page — centered card, mobile-friendly",
        "language": "css",
        "summary": "A complete login/register page: centered card, responsive, branded. The pattern every auth page uses.",
        "starter_code": "body {\n  margin: 0;\n  font-family: -apple-system, system-ui, sans-serif;\n  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);\n  min-height: 100vh;\n  display: flex;\n  align-items: center;\n  justify-content: center;\n  padding: 1rem;\n}\n\n.auth-card {\n  background: white;\n  border-radius: 16px;\n  padding: 2.5rem;\n  width: 100%;\n  max-width: 400px;\n  box-shadow: 0 20px 60px rgba(0,0,0,0.3);\n}\n\n.auth-card .logo {\n  text-align: center;\n  font-size: 2rem;\n  margin-bottom: 0.5rem;\n}\n\n.auth-card h1 {\n  text-align: center;\n  font-size: 1.4rem;\n  margin: 0 0 0.3rem 0;\n  color: #1a1a1a;\n}\n\n.auth-card .subtitle {\n  text-align: center;\n  color: #666;\n  font-size: 0.9rem;\n  margin-bottom: 2rem;\n}\n\n.form-group {\n  margin-bottom: 1.2rem;\n}\n\n.form-group label {\n  display: block;\n  font-size: 0.85rem;\n  font-weight: 600;\n  color: #333;\n  margin-bottom: 0.4rem;\n}\n\n.form-group input {\n  width: 100%;\n  padding: 0.7rem 0.9rem;\n  border: 2px solid #ddd;\n  border-radius: 8px;\n  font-size: 0.95rem;\n  outline: none;\n  transition: border-color 0.15s, box-shadow 0.15s;\n  box-sizing: border-box;\n}\n\n.form-group input:focus {\n  border-color: #667eea;\n  box-shadow: 0 0 0 3px rgba(102,126,234,0.2);\n}\n\n.btn-submit {\n  width: 100%;\n  background: #667eea;\n  color: white;\n  border: none;\n  padding: 0.8rem;\n  border-radius: 8px;\n  font-size: 1rem;\n  font-weight: 600;\n  cursor: pointer;\n  margin-top: 0.5rem;\n  transition: background 0.15s;\n}\n\n.btn-submit:hover {\n  background: #5568d3;\n}\n\n.auth-card .footer-link {\n  text-align: center;\n  margin-top: 1.5rem;\n  font-size: 0.88rem;\n  color: #666;\n}\n\n.auth-card .footer-link a {\n  color: #667eea;\n  text-decoration: none;\n  font-weight: 600;\n}",
        "html_template": "<div class=\"auth-card\">\n  <div class=\"logo\">&#9889;</div>\n  <h1>Welcome back</h1>\n  <p class=\"subtitle\">Log in to your account</p>\n  <form>\n    <div class=\"form-group\">\n      <label>Email</label>\n      <input type=\"email\" placeholder=\"you@example.com\" required>\n    </div>\n    <div class=\"form-group\">\n      <label>Password</label>\n      <input type=\"password\" placeholder=\"••••••••\" required>\n    </div>\n    <button type=\"submit\" class=\"btn-submit\">Log In</button>\n  </form>\n  <div class=\"footer-link\">\n    Don't have an account? <a href=\"#\">Sign up</a>\n  </div>\n</div>",
        "explanation": (
            "body is a flex container, centered — the card is always in the middle of the screen. "
            "background: linear-gradient — a nice purple gradient. Change it to match your brand. "
            "min-height: 100vh + padding: 1rem — fills the viewport, with a small margin on mobile. "
            "max-width: 400px + width: 100% — responsive: 400px on desktop, full width (minus padding) on mobile. "
            "box-shadow: 0 20px 60px — a big soft shadow makes the card 'float' above the gradient. "
            "border-radius: 16px — generous rounding, feels modern. "
            "Focus ring color matches the gradient (#667eea) — consistent branding. "
            "width: 100% on the button — full-width button, common in auth forms. "
            "box-sizing: border-box on inputs — critical! Without it, padding makes inputs wider than 100%."
        ),
        "try_changes": [
            ("Change the gradient from #667eea #764ba2 to #a0c000 #58a6ff", "green-to-blue gradient"),
            ("Change max-width: 400px to 350px", "narrower card"),
            ("Change border-radius: 16px to 8px", "less rounded — more 'corporate'"),
            ("Change the focus color from #667eea to #a0c000", "focus ring becomes green"),
            ("Change box-shadow: 0 20px 60px to 0 4px 12px", "smaller shadow — card feels flatter"),
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  HTML LABS
# ═══════════════════════════════════════════════════════════════════════════

_HTML_LABS = [
    {
        "slug": "html-tags",
        "category": "HTML",
        "title": "Common tags — h1, p, ul, a, img, div",
        "language": "html",
        "summary": "The 6 tags you'll use 90% of the time. Change the tag name, see the rendering change.",
        "starter_code": "<h1>This is a heading</h1>\n<p>This is a paragraph of text. Paragraphs have margin above and below.</p>\n<ul>\n  <li>First list item</li>\n  <li>Second list item</li>\n</ul>\n<a href=\"https://example.com\">This is a link</a>\n<div>This is a div — a generic container.</div>",
        "html_template": "",
        "explanation": (
            "h1-h6 — headings (h1 is largest, h6 smallest). Browsers add margin by default. "
            "p — paragraph. Block element, has margin. "
            "ul — unordered list (bullets). ol — ordered list (numbers). li — list item (must be inside ul/ol). "
            "a — anchor (link). href is the URL. target='_blank' opens in a new tab. "
            "img — image. src is the URL, alt is the description (required for accessibility). "
            "div — generic block container. span — generic inline container. Use them when no semantic tag fits."
        ),
        "try_changes": [
            ("Change h1 to h6", "text becomes much smaller"),
            ("Change <ul> to <ol>", "bullets become numbers"),
            ("Add target=\"_blank\" to the <a>", "link opens in a new tab"),
            ("Add <img src=\"https://placekitten.com/200/100\" alt=\"kitten\">", "image appears"),
        ],
    },
    {
        "slug": "html-form",
        "category": "HTML",
        "title": "Forms — input, label, button",
        "language": "html",
        "summary": "Forms collect user input. Each input needs a name and a label.",
        "starter_code": "<form>\n  <label>\n    Email:\n    <input type=\"email\" name=\"email\" placeholder=\"you@example.com\" required>\n  </label>\n  <label>\n    Password:\n    <input type=\"password\" name=\"password\" required>\n  </label>\n  <label>\n    Age:\n    <input type=\"number\" name=\"age\" min=\"18\" max=\"120\" value=\"25\">\n  </label>\n  <label>\n    Bio:\n    <textarea name=\"bio\" rows=\"3\" placeholder=\"Tell us about yourself\"></textarea>\n  </label>\n  <button type=\"submit\">Sign Up</button>\n</form>",
        "html_template": "",
        "explanation": (
            "form wraps the inputs. action is the URL to submit to, method is GET or POST. "
            "label ties text to an input (click the text to focus the input). "
            "input types: text, email, password, number, date, checkbox, radio, file, color, range. "
            "required — browser won't submit without a value. "
            "placeholder — grey hint text. "
            "value — default value. "
            "textarea — multi-line text input (rows = height in lines). "
            "button type='submit' — submits the form. type='button' — just a clickable button."
        ),
        "try_changes": [
            ("Change type=\"email\" to type=\"text\"", "no email validation — any text accepted"),
            ("Change type=\"number\" to type=\"range\"", "number input becomes a slider"),
            ("Add 'disabled' to the password input", "field becomes greyed out and uneditable"),
            ("Add <input type=\"checkbox\" name=\"agree\"> I agree", "adds a checkbox"),
            ("Wrap the form in <fieldset>...</fieldset>", "form gets a border"),
        ],
    },
    {
        "slug": "html-table",
        "category": "HTML",
        "title": "Tables — the right way (not for layout!)",
        "language": "html",
        "summary": "Use tables for TABULAR DATA only (not for page layout). thead, tbody, tr, th, td.",
        "starter_code": "<table>\n  <thead>\n    <tr>\n      <th>Name</th>\n      <th>Age</th>\n      <th>City</th>\n    </tr>\n  </thead>\n  <tbody>\n    <tr>\n      <td>Ada</td>\n      <td>36</td>\n      <td>London</td>\n    </tr>\n    <tr>\n      <td>Alan</td>\n      <td>41</td>\n      <td>Manchester</td>\n    </tr>\n  </tbody>\n</table>",
        "html_template": "",
        "explanation": (
            "table — the container. "
            "thead — table header (top row). tbody — table body. tfoot — table footer (rare). "
            "tr — table row. th — table header cell (bold, centered by default). td — table data cell. "
            "Add 'border: 1px solid black; border-collapse: collapse;' in a <style> tag to see borders. "
            "colspan='2' makes a cell span 2 columns. rowspan='2' spans 2 rows. "
            "NEVER use tables for page layout — use CSS grid/flexbox instead. Tables are for DATA only."
        ),
        "try_changes": [
            ("Add <style>table, th, td { border: 1px solid black; border-collapse: collapse; padding: 8px; }</style> at the top", "visible borders appear"),
            ("Change <td>Ada</td> to <td colspan=\"2\">Ada</td>", "Ada's cell spans 2 columns"),
            ("Add a third row with your own data", "table grows"),
            ("Add <caption>Users</caption> right after <table>", "table gets a title"),
        ],
    },
    {
        "slug": "html-semantic",
        "category": "HTML",
        "title": "Semantic tags — header, nav, main, article, footer",
        "language": "html",
        "summary": "Semantic tags describe the CONTENT, not just the look. Better for SEO and accessibility.",
        "starter_code": "<header>\n  <h1>My Blog</h1>\n  <nav>\n    <a href=\"/\">Home</a> |\n    <a href=\"/about\">About</a>\n  </nav>\n</header>\n<main>\n  <article>\n    <h2>First Post</h2>\n    <p>Published on <time datetime=\"2024-01-15\">January 15, 2024</time></p>\n    <p>This is the content of my first blog post.</p>\n  </article>\n</main>\n<footer>\n  <p>&copy; 2024 My Blog</p>\n</footer>",
        "html_template": "",
        "explanation": (
            "header — top of a page or section (logo, nav). "
            "nav — navigation links. "
            "main — the main content of the page (only one per page). "
            "article — a self-contained piece (a blog post, a news story, a forum comment). "
            "section — a thematic grouping of content. "
            "aside — sidebar content (related links, ads). "
            "footer — bottom of a page or section (copyright, links). "
            "time — a date (datetime attribute is machine-readable). "
            "Why use these instead of div? Screen readers use them to navigate. Search engines use them to understand the page."
        ),
        "try_changes": [
            ("Add <aside><h3>Related</h3><ul><li>Post 2</li></ul></aside> inside <main>", "sidebar appears"),
            ("Change <p>Published on <time...> to just <p>Published on January 15, 2024</p>", "loses the machine-readable date"),
            ("Add a second <article> below the first", "two articles in the main section"),
        ],
    },
    {
        "slug": "html-links-images",
        "category": "HTML",
        "title": "Links and images — the web's basics",
        "language": "html",
        "summary": "Links connect pages. Images display pictures. Both use URL attributes (href / src).",
        "starter_code": "<h2>Links</h2>\n<a href=\"https://example.com\">External link</a><br>\n<a href=\"/about\">Internal link</a><br>\n<a href=\"#section1\">Jump to section</a><br>\n<a href=\"mailto:hello@example.com\">Email link</a><br>\n<a href=\"tel:+1234567890\">Phone link</a>\n\n<h2>Images</h2>\n<img src=\"https://placekitten.com/200/150\" alt=\"A kitten\" width=\"200\" height=\"150\">\n<img src=\"https://placekitten.com/100/100\" alt=\"Another kitten\" style=\"border-radius: 50%;\">",
        "html_template": "",
        "explanation": (
            "a (anchor) — link. href is the destination. "
            "  External: https://example.com — full URL. "
            "  Internal: /about — absolute path on same domain. "
            "  Relative: about.html — relative to current page. "
            "  Anchor: #section1 — jumps to element with id='section1'. "
            "  mailto: — opens email client. tel: — opens phone dialer (mobile). "
            "img — image. src is the URL. alt is REQUIRED (accessibility + SEO). "
            "width/height in pixels — set them to prevent layout shift while loading. "
            "Always set width/height OR use CSS aspect-ratio to avoid CLS (Cumulative Layout Shift)."
        ),
        "try_changes": [
            ("Add target=\"_blank\" to the external link", "opens in new tab"),
            ("Change the image src to a different URL", "different image"),
            ("Remove the alt attribute from the first image", "image still shows, but screen readers can't describe it"),
            ("Add loading=\"lazy\" to the images", "images only load when scrolled into view (performance)"),
        ],
    },
    {
        "slug": "html-entities",
        "category": "HTML",
        "title": "HTML entities — &lt; &gt; &amp; &copy; &mdash;",
        "language": "html",
        "summary": "Special characters that need a code because they'd otherwise be parsed as HTML.",
        "starter_code": "<p>Less than: &lt;  Greater than: &gt;</p>\n<p>Ampersand: &amp;  Quote: &quot;  Apostrophe: &apos;</p>\n<p>Copyright: &copy;  Trademark: &trade;  Registered: &reg;</p>\n<p>Em dash: &mdash;  En dash: &ndash;  Non-breaking space: &nbsp;here</p>\n<p>Arrow: &rarr;  Check: &check;  Cross: &cross;</p>\n<p>Code example: &lt;div class=&quot;card&quot;&gt;Hello&lt;/div&gt;</p>",
        "html_template": "",
        "explanation": (
            "Entities start with & and end with ;. "
            "MUST-USE: < → &lt;  > → &gt;  & → &amp;  (otherwise they're parsed as HTML tags). "
            "Useful: &copy; (©), &trade; (™), &mdash; (—), &nbsp; (non-breaking space — prevents line wrap). "
            "Numbers: &#60; for <  &#169; for ©  (any Unicode char by code point). "
            "To SHOW HTML code on a page (like in a tutorial), every < > and & must be escaped."
        ),
        "try_changes": [
            ("Change &lt; to just <", "the rest of the line becomes a tag and may disappear"),
            ("Change &mdash; to &ndash;", "em dash (long) becomes en dash (short)"),
            ("Add &hearts; somewhere", "heart symbol appears"),
            ("Add &#128512; (smiley emoji by codepoint)", "😀 appears"),
        ],
    },

    # ─── HTML labs for building REAL webpages ─────────────────────────
    # Complete page structures, not just snippets.

    {
        "slug": "html-boilerplate",
        "category": "HTML",
        "title": "HTML5 boilerplate — the complete starting template",
        "language": "html",
        "summary": "Every HTML page starts with this. DOCTYPE, html, head with meta tags, body. Copy-paste this as your starting point.",
        "starter_code": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <meta name=\"description\" content=\"My ML dashboard\">\n  <meta name=\"author\" content=\"Your Name\">\n  <title>My App — Home</title>\n  <link rel=\"stylesheet\" href=\"/static/style.css\">\n  <link rel=\"icon\" href=\"/static/favicon.ico\" type=\"image/x-icon\">\n</head>\n<body>\n  <!-- Page content goes here -->\n  <h1>Hello, World!</h1>\n  <p>This is a complete HTML5 page.</p>\n\n  <script src=\"/static/app.js\"></script>\n</body>\n</html>",
        "html_template": "",
        "explanation": (
            "<!DOCTYPE html> — tells the browser this is HTML5 (not HTML 4 or XHTML). Always first line. "
            "<html lang='en'> — the root element. lang helps screen readers + search engines. "
            "<head> — metadata the browser doesn't render: charset, viewport, title, CSS links. "
            "<meta charset='UTF-8'> — character encoding. Without it, special chars (é, →, emoji) break. "
            "<meta name='viewport' ...> — CRITICAL for mobile. Without it, phones show a tiny zoomed-out version. "
            "<meta name='description'> — what Google shows in search results. 150 chars max. "
            "<title> — appears in the browser tab + search results. Keep under 60 chars. "
            "<link rel='stylesheet'> — load CSS. Always in the head. "
            "<link rel='icon'> — the favicon (tiny icon in the browser tab). "
            "<script> — load JavaScript. Put at the END of body so the page renders first. "
            "Comments: <!-- text --> — invisible in the browser, visible in 'View Source'."
        ),
        "try_changes": [
            ("Change lang=\"en\" to lang=\"es\"", "screen readers switch to Spanish pronunciation"),
            ("Change the title to 'My Cool App — Dashboard'", "browser tab text changes"),
            ("Remove the viewport meta tag", "on mobile, the page becomes tiny and zoomed out"),
            ("Add <meta name=\"theme-color\" content=\"#a0c000\">", "mobile browser address bar turns green"),
            ("Change charset from UTF-8 to ISO-8859-1", "special characters may break"),
        ],
    },
    {
        "slug": "html-dashboard-page",
        "category": "HTML",
        "title": "Complete dashboard page — sidebar + KPIs + charts + table",
        "language": "html",
        "summary": "The full HTML structure of a data-science dashboard. Semantic tags: header, aside, main, section, article.",
        "starter_code": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>ML Dashboard</title>\n</head>\n<body>\n  <div class=\"dashboard\">\n    <!-- Sidebar navigation -->\n    <aside class=\"sidebar\">\n      <div class=\"logo\">&#9889; ML Dash</div>\n      <nav>\n        <a href=\"/\" class=\"active\">Dashboard</a>\n        <a href=\"/models\">Models</a>\n        <a href=\"/datasets\">Datasets</a>\n        <a href=\"/experiments\">Experiments</a>\n        <a href=\"/settings\">Settings</a>\n      </nav>\n    </aside>\n\n    <!-- Main content -->\n    <main class=\"main\">\n      <header class=\"page-header\">\n        <h1>Dashboard Overview</h1>\n        <button class=\"btn-primary\">+ New Model</button>\n      </header>\n\n      <!-- KPI row -->\n      <section class=\"kpi-row\">\n        <article class=\"kpi\">\n          <div class=\"label\">Total Models</div>\n          <div class=\"value\">24</div>\n          <div class=\"change up\">+3 this week</div>\n        </article>\n        <article class=\"kpi\">\n          <div class=\"label\">Avg Accuracy</div>\n          <div class=\"value\">91.4%</div>\n          <div class=\"change up\">+2.1%</div>\n        </article>\n        <article class=\"kpi\">\n          <div class=\"label\">Avg Latency</div>\n          <div class=\"value\">38ms</div>\n          <div class=\"change down\">-12ms</div>\n        </article>\n      </section>\n\n      <!-- Charts grid -->\n      <section class=\"charts-grid\">\n        <article class=\"chart-card\">\n          <h3>Accuracy Over Time</h3>\n          <div class=\"chart-area\">[ Line chart ]</div>\n        </article>\n        <article class=\"chart-card\">\n          <h3>Model Comparison</h3>\n          <div class=\"chart-area\">[ Bar chart ]</div>\n        </article>\n      </section>\n\n      <!-- Data table -->\n      <section class=\"table-section\">\n        <h2>Recent Models</h2>\n        <table>\n          <thead>\n            <tr>\n              <th>Name</th>\n              <th>Type</th>\n              <th>Accuracy</th>\n              <th>Status</th>\n            </tr>\n          </thead>\n          <tbody>\n            <tr>\n              <td>RandomForest v2</td>\n              <td>Classifier</td>\n              <td>94.2%</td>\n              <td><span class=\"badge success\">Trained</span></td>\n            </tr>\n            <tr>\n              <td>XGBoost v1</td>\n              <td>Classifier</td>\n              <td>95.1%</td>\n              <td><span class=\"badge success\">Trained</span></td>\n            </tr>\n          </tbody>\n        </table>\n      </section>\n    </main>\n  </div>\n</body>\n</html>",
        "html_template": "",
        "explanation": (
            "Semantic HTML uses tags that describe MEANING, not just appearance: "
            "  <aside> — sidebar content, tangential to the main content. "
            "  <main> — the main content of the page (only one per page). "
            "  <header> — introductory content (page title + action button). "
            "  <section> — a thematic grouping (KPI row, charts, table). "
            "  <article> — a self-contained piece (one KPI card, one chart card). "
            "  <nav> — navigation links. "
            "Why use semantic tags instead of div? "
            "  1. Screen readers use them to navigate (accessibility). "
            "  2. Search engines understand the page structure (SEO). "
            "  3. CSS targeting is clearer: .sidebar vs #sidebar vs aside. "
            "The structure: dashboard > [sidebar (aside), main > (header, sections)] — clean hierarchy."
        ),
        "try_changes": [
            ("Add a 4th KPI <article> inside .kpi-row", "4-column KPI row"),
            ("Add a new <section> below the table with a form", "form section appears"),
            ("Change <aside class=\"sidebar\"> to just <div class=\"sidebar\">", "loses semantic meaning (still works visually)"),
            ("Add <footer> at the bottom of <main>", "footer appears at the bottom of the main content"),
        ],
    },
    {
        "slug": "html-complete-form",
        "category": "HTML",
        "title": "Complete form — all input types + validation",
        "language": "html",
        "summary": "Every input type in one form: text, email, password, number, range, date, checkbox, radio, select, textarea, file.",
        "starter_code": "<form action=\"/submit\" method=\"post\">\n  <h2>Train a New Model</h2>\n\n  <!-- Text -->\n  <label>Model Name:\n    <input type=\"text\" name=\"model_name\" placeholder=\"My RandomForest\" required minlength=\"3\">\n  </label>\n\n  <!-- Email -->\n  <label>Email (for notifications):\n    <input type=\"email\" name=\"email\" required>\n  </label>\n\n  <!-- Select dropdown -->\n  <label>Algorithm:\n    <select name=\"algorithm\">\n      <option value=\"rf\">Random Forest</option>\n      <option value=\"xgb\">XGBoost</option>\n      <option value=\"lr\">Linear Regression</option>\n      <option value=\"nn\">Neural Network</option>\n    </select>\n  </label>\n\n  <!-- Number with min/max/step -->\n  <label>Max Depth:\n    <input type=\"number\" name=\"max_depth\" value=\"10\" min=\"1\" max=\"100\" step=\"1\">\n  </label>\n\n  <!-- Range slider -->\n  <label>Learning Rate: <span id=\"lr-val\">0.01</span>\n    <input type=\"range\" name=\"learning_rate\" min=\"0.001\" max=\"1.0\" step=\"0.001\" value=\"0.01\">\n  </label>\n\n  <!-- Radio buttons -->\n  <fieldset>\n    <legend>Task Type:</legend>\n    <label><input type=\"radio\" name=\"task\" value=\"classification\" checked> Classification</label>\n    <label><input type=\"radio\" name=\"task\" value=\"regression\"> Regression</label>\n  </fieldset>\n\n  <!-- Checkboxes -->\n  <fieldset>\n    <legend>Features to use:</legend>\n    <label><input type=\"checkbox\" name=\"features\" value=\"age\" checked> Age</label>\n    <label><input type=\"checkbox\" name=\"features\" value=\"income\" checked> Income</label>\n    <label><input type=\"checkbox\" name=\"features\" value=\"education\"> Education</label>\n  </fieldset>\n\n  <!-- Date -->\n  <label>Train until date:\n    <input type=\"date\" name=\"train_until\">\n  </label>\n\n  <!-- Textarea -->\n  <label>Notes:\n    <textarea name=\"notes\" rows=\"3\" placeholder=\"Any special instructions...\"></textarea>\n  </label>\n\n  <!-- File upload -->\n  <label>Upload dataset (CSV):\n    <input type=\"file\" name=\"dataset\" accept=\".csv\">\n  </label>\n\n  <!-- Hidden field -->\n  <input type=\"hidden\" name=\"user_id\" value=\"42\">\n\n  <!-- Submit + Reset -->\n  <button type=\"submit\">Start Training</button>\n  <button type=\"reset\">Reset Form</button>\n</form>",
        "html_template": "",
        "explanation": (
            "Every input type serves a different purpose: "
            "  text — single-line text. "
            "  email — validates email format, shows @ on mobile keyboards. "
            "  password — masks characters. "
            "  number — spinner, min/max/step validation. "
            "  range — slider. Pair with <span> to show the value (needs JS to update). "
            "  date — native date picker. "
            "  checkbox — multiple selections (same name, different values). "
            "  radio — single selection (same name, different values). Always one selected. "
            "  select — dropdown. <option> for each choice. "
            "  textarea — multi-line text. rows = height. "
            "  file — file upload. accept='.csv' filters the file picker. "
            "  hidden — data you want in the form submission but not visible to the user. "
            "fieldset + legend — groups related inputs (like radio buttons) with a label. "
            "required — browser won't submit without a value. "
            "minlength/maxlength — text length validation."
        ),
        "try_changes": [
            ("Change type=\"text\" to type=\"password\" for model_name", "text becomes masked dots"),
            ("Add 'multiple' to the file input", "allows uploading multiple files"),
            ("Add 'disabled' to the select", "dropdown becomes greyed out"),
            ("Change type=\"number\" to type=\"range\" for max_depth", "number becomes a slider"),
            ("Add <option value=\"\" selected disabled>Select...</option> as the first option in the select", "adds a placeholder"),
        ],
    },
    {
        "slug": "html-data-table",
        "category": "HTML",
        "title": "Complete data table — caption, thead, tbody, colspan",
        "language": "html",
        "summary": "A proper data table with caption, header, body, footer, and cells that span multiple columns.",
        "starter_code": "<table>\n  <caption>Model Benchmark Results — Q3 2024</caption>\n  <thead>\n    <tr>\n      <th rowspan=\"2\">Model</th>\n      <th colspan=\"2\">Accuracy</th>\n      <th colspan=\"2\">Latency (ms)</th>\n      <th rowspan=\"2\">Status</th>\n    </tr>\n    <tr>\n      <th>Train</th>\n      <th>Test</th>\n      <th>Train</th>\n      <th>Test</th>\n    </tr>\n  </thead>\n  <tbody>\n    <tr>\n      <td>RandomForest</td>\n      <td>0.982</td>\n      <td>0.942</td>\n      <td>120</td>\n      <td>12</td>\n      <td><span class=\"badge success\">Trained</span></td>\n    </tr>\n    <tr>\n      <td>XGBoost</td>\n      <td>0.991</td>\n      <td>0.951</td>\n      <td>85</td>\n      <td>8</td>\n      <td><span class=\"badge success\">Trained</span></td>\n    </tr>\n    <tr>\n      <td>NeuralNet</td>\n      <td>0.978</td>\n      <td>0.938</td>\n      <td>2400</td>\n      <td>45</td>\n      <td><span class=\"badge fail\">Failed</span></td>\n    </tr>\n  </tbody>\n  <tfoot>\n    <tr>\n      <td><strong>Average</strong></td>\n      <td><strong>0.984</strong></td>\n      <td><strong>0.944</strong></td>\n      <td><strong>868</strong></td>\n      <td><strong>22</strong></td>\n      <td>—</td>\n    </tr>\n  </tfoot>\n</table>",
        "html_template": "",
        "explanation": (
            "caption — the table's title. Appears above the table. Important for accessibility. "
            "thead — header rows. Can have MULTIPLE rows (like here: one for groups, one for sub-columns). "
            "tbody — the actual data rows. "
            "tfoot — footer rows (totals, averages). Appears at the bottom. "
            "rowspan='2' — this cell spans 2 rows (the Model header covers both header rows). "
            "colspan='2' — this cell spans 2 columns (Accuracy header covers Train + Test columns). "
            "Use colspan/rowspan for grouped headers — common in benchmark tables. "
            "th — header cell (bold, centered by default). td — data cell (normal). "
            "Always use <thead> / <tbody> — CSS targets them separately (e.g. .data-table thead)."
        ),
        "try_changes": [
            ("Add a new <tr> in tbody with a new model", "table grows by one row"),
            ("Change rowspan=\"2\" to rowspan=\"1\" on the Model header", "header structure breaks — Model only covers first row"),
            ("Add a new column: add a <th> in thead and a <td> in each tbody row", "table gets wider"),
            ("Remove the <caption>", "table loses its title"),
            ("Add a 'colgroup' to set column widths: <colgroup><col style=\"width:200px\"><col><col></colgroup>", "first column becomes fixed width"),
        ],
    },
    {
        "slug": "html-article-page",
        "category": "HTML",
        "title": "Article/blog page — complete content layout",
        "language": "html",
        "summary": "A blog post or article page with header, metadata, content blocks, code blocks, and a footer.",
        "starter_code": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>Understanding Random Forest — ML Blog</title>\n</head>\n<body>\n  <article>\n    <header>\n      <h1>Understanding Random Forest</h1>\n      <p class=\"meta\">\n        By <a href=\"/author/ada\">Ada Lovelace</a> ·\n        <time datetime=\"2024-09-01\">September 1, 2024</time> ·\n        8 min read\n      </p>\n      <p class=\"tags\">\n        <span class=\"tag\">machine-learning</span>\n        <span class=\"tag\">random-forest</span>\n        <span class=\"tag\">scikit-learn</span>\n      </p>\n    </header>\n\n    <section>\n      <h2>What is Random Forest?</h2>\n      <p>Random Forest is an <em>ensemble learning</em> method that combines\n      multiple <strong>decision trees</strong> to improve accuracy and reduce\n      overfitting. It was developed by Leo Breiman in 2001.</p>\n\n      <blockquote>\n        \"Random forests are a combination of tree predictors such that each\n        tree depends on the values of a random vector sampled independently.\"\n        — Breiman, 2001\n      </blockquote>\n    </section>\n\n    <section>\n      <h2>How it works</h2>\n      <p>The algorithm works in 3 steps:</p>\n      <ol>\n        <li>Draw a random sample from the training data (with replacement).</li>\n        <li>Train a decision tree on the sample, using a random subset of features.</li>\n        <li>Repeat N times. The final prediction is the average (regression) or\n            majority vote (classification).</li>\n      </ol>\n\n      <h3>Code example</h3>\n      <pre><code>from sklearn.ensemble import RandomForestClassifier\nfrom sklearn.datasets import load_iris\n\nX, y = load_iris(return_X_y=True)\nclf = RandomForestClassifier(n_estimators=100, max_depth=10)\nclf.fit(X, y)\n\nprint(f\"Accuracy: {clf.score(X, y):.3f}\")</code></pre>\n    </section>\n\n    <section>\n      <h2>When to use it</h2>\n      <table>\n        <thead>\n          <tr><th>Pros</th><th>Cons</th></tr>\n        </thead>\n        <tbody>\n          <tr>\n            <td>High accuracy</td>\n            <td>Slow on large datasets</td>\n          </tr>\n          <tr>\n            <td>Handles non-linear patterns</td>\n            <td>Hard to interpret</td>\n          </tr>\n        </tbody>\n      </table>\n    </section>\n\n    <footer>\n      <p>If you enjoyed this article, please share it.</p>\n      <nav class=\"article-nav\">\n        <a href=\"/blog/previous\">&larr; Previous: Decision Trees</a>\n        <a href=\"/blog/next\">Next: XGBoost &rarr;</a>\n      </nav>\n    </footer>\n  </article>\n</body>\n</html>",
        "html_template": "",
        "explanation": (
            "article — a self-contained piece of content (a blog post, news story, paper). "
            "  Can have its own <header> and <footer> — they're scoped to the article, not the page. "
            "<time datetime='2024-09-01'> — machine-readable date. Search engines + calendars use it. "
            "<blockquote> — a quoted block. Browsers indent it by default. "
            "<pre><code> — preformatted text + code. Whitespace is preserved (indentation shows). "
            "  Always use <pre> around <code> to preserve line breaks. "
            "<ol> — ordered list (1, 2, 3...). <ul> — unordered (bullets). "
            "<em> — emphasis (italic). <strong> — strong importance (bold). "
            "  These are SEMANTIC, not visual. Screen readers interpret them. "
            "<nav class='article-nav'> — prev/next navigation at the bottom of the article."
        ),
        "try_changes": [
            ("Change <ol> to <ul>", "numbered list becomes bullets"),
            ("Add a <figure> with an <img> and <figcaption>", "image with caption appears"),
            ("Change <blockquote> to just <p>", "quote loses its indentation"),
            ("Add <hr> between sections", "horizontal line separates sections"),
            ("Change the <time> datetime to '2024-12-25'", "machine-readable date changes"),
        ],
    },
    {
        "slug": "html-login-page",
        "category": "HTML",
        "title": "Login page — complete auth form",
        "language": "html",
        "summary": "A complete login page with email/password, remember me, forgot password, and social login buttons.",
        "starter_code": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>Log In — MyApp</title>\n</head>\n<body>\n  <main class=\"auth-container\">\n    <div class=\"auth-card\">\n      <div class=\"logo\">&#9889;</div>\n      <h1>Welcome back</h1>\n      <p class=\"subtitle\">Log in to your account</p>\n\n      <form action=\"/login\" method=\"post\">\n        <div class=\"form-group\">\n          <label for=\"email\">Email</label>\n          <input type=\"email\" id=\"email\" name=\"email\"\n                 placeholder=\"you@example.com\" required autocomplete=\"email\">\n        </div>\n\n        <div class=\"form-group\">\n          <label for=\"password\">Password</label>\n          <input type=\"password\" id=\"password\" name=\"password\"\n                 placeholder=\"••••••••\" required autocomplete=\"current-password\"\n                 minlength=\"8\">\n        </div>\n\n        <div class=\"form-row\">\n          <label class=\"checkbox-label\">\n            <input type=\"checkbox\" name=\"remember\" value=\"true\">\n            Remember me\n          </label>\n          <a href=\"/forgot-password\" class=\"forgot-link\">Forgot password?</a>\n        </div>\n\n        <button type=\"submit\" class=\"btn-submit\">Log In</button>\n      </form>\n\n      <div class=\"divider\"><span>or</span></div>\n\n      <div class=\"social-buttons\">\n        <button class=\"btn-social google\">Continue with Google</button>\n        <button class=\"btn-social github\">Continue with GitHub</button>\n      </div>\n\n      <p class=\"footer-link\">\n        Don't have an account? <a href=\"/register\">Sign up</a>\n      </p>\n    </div>\n  </main>\n</body>\n</html>",
        "html_template": "",
        "explanation": (
            "autocomplete='email' / 'current-password' — tells the browser's password manager what to fill. "
            "  CRITICAL for UX — without it, browsers can't auto-fill logins. "
            "required — browser won't submit without a value. "
            "minlength='8' — minimum 8 characters (basic password policy). "
            "type='password' — masks characters. "
            "Checkbox + link on the same row — the 'remember me' + 'forgot password' pattern every auth form uses. "
            "Divider with 'or' — separates email login from social login. "
            "Social buttons — Google, GitHub, etc. Each would POST to a different endpoint. "
            "label class='checkbox-label' — lets CSS style the checkbox + text as a unit. "
            "The form method='post' — NEVER use GET for login (password would appear in the URL + browser history)."
        ),
        "try_changes": [
            ("Add autocomplete=\"new-password\" to the password field", "tells browser this is a NEW password (for registration)"),
            ("Add a <input type=\"hidden\" name=\"next\" value=\"/dashboard\">", "redirects to /dashboard after login"),
            ("Change type=\"password\" to type=\"text\"", "password becomes visible (useful for debugging)"),
            ("Add 'maxlength=\"72\"' to the password input", "limits password to 72 chars (bcrypt max)"),
            ("Add a third social button: Continue with Apple", "new social login option"),
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  PYTHON LABS
# ═══════════════════════════════════════════════════════════════════════════

_PYTHON_LABS = [
    {
        "slug": "py-variables",
        "category": "Python",
        "title": "Variables — assignment and reassignment",
        "language": "python",
        "summary": "x = 5 binds the name x to the int 5. Reassign x = 'hello' rebinds it to a string. Python is dynamically typed.",
        "starter_code": "x = 5\nprint('x =', x, 'type:', type(x).__name__)\n\nx = 'hello'\nprint('x =', x, 'type:', type(x).__name__)\n\nx = [1, 2, 3]\nprint('x =', x, 'type:', type(x).__name__)\n\n# Multiple assignment\na, b, c = 1, 2, 3\nprint('a, b, c =', a, b, c)\n\n# Swap without a temp variable\na, b = b, a\nprint('after swap: a =', a, 'b =', b)",
        "html_template": "",
        "explanation": (
            "x = 5 creates an int object 5 in memory and binds the name x to it. "
            "x = 'hello' doesn't change the int — it rebinds x to a new str object. "
            "This is 'dynamic typing': the type lives on the OBJECT, not the NAME. "
            "Multiple assignment: a, b, c = 1, 2, 3 — Python packs the right side into a tuple, unpacks on the left. "
            "Swap: a, b = b, a — the right side is evaluated FIRST (as a tuple), then unpacked. No temp variable needed."
        ),
        "try_changes": [
            ("Change x = 5 to x = 5.5", "type becomes 'float'"),
            ("Change x = 'hello' to x = True", "type becomes 'bool'"),
            ("Add x = None  after the list assignment", "type becomes 'NoneType'"),
            ("Change a, b, c = 1, 2, 3 to a, b, c = 'abc'", "a='a', b='b', c='c' — strings are iterable"),
        ],
    },
    {
        "slug": "py-loops",
        "category": "Python",
        "title": "Loops — for, while, comprehensions",
        "language": "python",
        "summary": "for iterates over any iterable. while runs until a condition is false. Comprehensions build lists in one line.",
        "starter_code": "# for loop over a range\nfor i in range(5):\n    print('range:', i)\n\n# for loop over a list\nfruits = ['apple', 'banana', 'cherry']\nfor f in fruits:\n    print('fruit:', f)\n\n# for loop with enumerate (index + value)\nfor i, f in enumerate(fruits):\n    print(f'{i}: {f}')\n\n# while loop\nn = 10\nwhile n > 1:\n    n //= 2\n    print('n =', n)\n\n# List comprehension (Pythonic)\nsquares = [x*x for x in range(5)]\nprint('squares:', squares)\n\n# Comprehension with filter\nevens = [x for x in range(10) if x % 2 == 0]\nprint('evens:', evens)",
        "html_template": "",
        "explanation": (
            "for variable in iterable: runs the loop body once per item. "
            "range(5) produces 0,1,2,3,4. range(2, 5) produces 2,3,4. range(0, 10, 2) produces 0,2,4,6,8. "
            "enumerate(iterable) yields (index, value) pairs — use it instead of range(len(iterable)). "
            "while condition: runs while condition is True. Risk: infinite loop if condition never becomes False. "
            "List comprehension: [expr for var in iter if cond] — faster than a for+append loop. "
            "Dict comprehension: {k: v for k, v in pairs}. Set comprehension: {x for x in iter}."
        ),
        "try_changes": [
            ("Change range(5) to range(2, 10)", "loop runs from 2 to 9"),
            ("Change range(5) to range(0, 10, 2)", "steps by 2: 0,2,4,6,8"),
            ("Change 'while n > 1' to 'while n > 0'", "extra iteration when n becomes 1"),
            ("Change squares to [x*x for x in range(5) if x % 2 == 0]", "only squares of evens: [0, 4, 16]"),
            ("Add 'break' inside the for loop after the first print", "loop exits after first iteration"),
        ],
    },
    {
        "slug": "py-functions",
        "category": "Python",
        "title": "Functions, args, kwargs, defaults",
        "language": "python",
        "summary": "def name(params): ... return value. *args collects positional, **kwargs collects keyword.",
        "starter_code": "def greet(name, greeting='Hello', shout=False):\n    msg = f'{greeting}, {name}!'\n    if shout:\n        msg = msg.upper()\n    return msg\n\n# Positional args\nprint(greet('Ada'))\n\n# Keyword args (order doesn't matter)\nprint(greet(greeting='Hi', name='Alan'))\n\n# Default arg used\nprint(greet('Bob', shout=True))\n\n# *args — collect extra positional into a tuple\ndef sum_all(*nums):\n    return sum(nums)\nprint('sum:', sum_all(1, 2, 3, 4, 5))\n\n# **kwargs — collect extra keyword into a dict\ndef show_config(**opts):\n    for k, v in opts.items():\n        print(f'  {k}: {v}')\nshow_config(debug=True, port=8080, host='localhost')",
        "html_template": "",
        "explanation": (
            "def name(params): body return value. Default args use '=' — evaluated ONCE at def time "
            "(mutable defaults like def f(x=[]) are a famous footgun!). "
            "*args collects extra positional args into a tuple. **kwargs collects extra keyword args into a dict. "
            "Order: positional, *args, keyword-only, **kwargs. "
            "Passing *list and **dict unpacks them into separate args: f(*[1,2,3]) is f(1, 2, 3). "
            "Functions are first-class — you can pass them as args, return them, store in variables."
        ),
        "try_changes": [
            ("Change greeting='Hello' to greeting='Hi'", "default greeting changes"),
            ("Add a new parameter punctuation='!' and append it to msg", "greeting ends with the punctuation"),
            ("Change sum_all(1,2,3,4,5) to sum_all(*range(1, 6))", "unpacks range into args — same result"),
            ("Call greet() with no args", "TypeError — name is required"),
        ],
    },
    {
        "slug": "py-lists",
        "category": "Python",
        "title": "Lists — append, slice, sort, comprehensions",
        "language": "python",
        "summary": "Lists are ordered, mutable, indexed. The most-used Python data structure.",
        "starter_code": "# Create\nnums = [3, 1, 4, 1, 5, 9, 2, 6]\nprint('original:', nums)\n\n# Indexing (0-based, negative from end)\nprint('first:', nums[0], 'last:', nums[-1])\n\n# Slicing [start:stop:step] — stop is EXCLUSIVE\nprint('first 3:', nums[:3])\nprint('last 3:', nums[-3:])\nprint('every other:', nums[::2])\nprint('reversed:', nums[::-1])\n\n# Mutating\nnums.append(7)\nprint('after append:', nums)\nnums.extend([8, 9])\nprint('after extend:', nums)\nnums.insert(0, 0)\nprint('after insert:', nums)\nnums.remove(1)  # removes FIRST 1\nprint('after remove(1):', nums)\n\n# Sorting\nsorted_nums = sorted(nums)\nprint('sorted:', sorted_nums)\nnums.sort(reverse=True)\nprint('reverse sorted in place:', nums)\n\n# Comprehension\ndoubled = [x * 2 for x in nums]\nprint('doubled:', doubled)",
        "html_template": "",
        "explanation": (
            "Lists are arrays that grow/shrink. Indexed 0, 1, 2, ... and -1, -2, -3 from the end. "
            "slice [start:stop:step] — start INCLUSIVE, stop EXCLUSIVE. nums[1:4] gives indices 1, 2, 3. "
            "Omitting start/stop means 'from beginning' / 'to end'. nums[::-1] reverses. "
            "append(x) adds to end. extend(iter) adds all from iter. insert(i, x) puts x at index i. "
            "remove(x) removes the FIRST x. pop() removes and returns the last. "
            "sort() sorts in place (returns None). sorted() returns a new sorted list (doesn't mutate). "
            "Comprehension [expr for x in list if cond] — faster than a for+append loop."
        ),
        "try_changes": [
            ("Change nums[:3] to nums[3:]", "last 5 instead of first 3"),
            ("Change nums[::2] to nums[::3]", "every 3rd element"),
            ("Change nums.sort(reverse=True) to nums.sort()", "ascending order"),
            ("Change [x * 2 for x in nums] to [x * 2 for x in nums if x > 4]", "only doubles values > 4"),
            ("Add nums.clear()", "empties the list"),
        ],
    },
    {
        "slug": "py-dicts",
        "category": "Python",
        "title": "Dictionaries — key/value storage",
        "language": "python",
        "summary": "dicts map keys to values. O(1) lookup. Insertion-ordered since Python 3.7.",
        "starter_code": "# Create\nperson = {\n    'name': 'Ada',\n    'age': 36,\n    'city': 'London',\n    'skills': ['Python', 'ML'],\n}\n\n# Access\nprint('name:', person['name'])\nprint('age:', person.get('age'))\nprint('phone (default):', person.get('phone', 'N/A'))  # no KeyError\n\n# Add / update\nperson['email'] = 'ada@example.com'\nperson['age'] = 37\nprint('after add/update:', person)\n\n# Iterate\nfor key in person:\n    print(f'  {key}: {person[key]}')\n\nfor key, value in person.items():\n    print(f'  {key} -> {value}')\n\n# Delete\ndel person['email']\nage = person.pop('age')\nprint(f'popped age: {age}, remaining keys: {list(person.keys())}')\n\n# Dict comprehension\nsquares = {n: n*n for n in range(5)}\nprint('squares:', squares)",
        "html_template": "",
        "explanation": (
            "dicts are hash tables — keys must be hashable (str, int, tuple, frozenset; NOT list or dict). "
            "person['key'] raises KeyError if missing. person.get('key', default) returns default if missing. "
            "items() yields (key, value) pairs. keys() yields keys. values() yields values. "
            "del d[k] removes key k. d.pop(k) removes and returns the value. "
            "Dict comprehension: {k_expr: v_expr for item in iter if cond}. "
            "Useful: dict(zip(keys, values)) builds a dict from two lists. "
            "Counter, defaultdict, OrderedDict in collections module for special cases."
        ),
        "try_changes": [
            ("Change person['name'] to person['phone']", "KeyError"),
            ("Change .get('phone', 'N/A') to .get('phone')", "returns None instead of 'N/A'"),
            ("Add 'skills' to the iteration filter — skip non-string values", "more complex iteration"),
            ("Change squares to {n: n*n for n in range(10) if n % 2 == 0}", "only even squares"),
        ],
    },
    {
        "slug": "py-if-else",
        "category": "Python",
        "title": "if / elif / else + ternary",
        "language": "python",
        "summary": "Conditional execution. Truthy values run the if branch; falsy values run else.",
        "starter_code": "# Basic if/else\nscore = 78\nif score >= 90:\n    grade = 'A'\nelif score >= 80:\n    grade = 'B'\nelif score >= 70:\n    grade = 'C'\nelse:\n    grade = 'F'\nprint(f'score {score} -> grade {grade}')\n\n# Truthy vs falsy\n# Falsy: False, None, 0, 0.0, '', [], {}, set()\n# Truthy: everything else\nvalues = [0, '', [], None, 1, 'hello', [1], {1: 2}]\nfor v in values:\n    print(f'{v!r:>10} -> {bool(v)}')\n\n# Ternary (one-line if/else)\nx = 10\nparity = 'even' if x % 2 == 0 else 'odd'\nprint(f'{x} is {parity}')\n\n# 'in' check\nfruits = ['apple', 'banana']\nprint('apple in fruits:', 'apple' in fruits)\nprint('cherry in fruits:', 'cherry' in fruits)",
        "html_template": "",
        "explanation": (
            "if condition: runs the block if condition is truthy. elif = 'else if'. else runs if nothing matched. "
            "Python has many falsy values: False, None, 0, 0.0, empty string '', empty list [], empty dict {}, empty set. "
            "Everything else is truthy — including non-empty containers, non-zero numbers, and any object. "
            "Ternary: value_if_true if condition else value_if_false — read it as 'X if condition else Y'. "
            "in checks membership: 'x' in [1, 2, 3], 'k' in dict, 'a' in 'apple'. "
            "Avoid '== True' — just use 'if x:' (Pythonic)."
        ),
        "try_changes": [
            ("Change score = 78 to score = 95", "grade becomes A"),
            ("Change score = 78 to score = 50", "grade becomes F"),
            ("Add a value 0.0 to the values list", "0.0 is falsy too"),
            ("Change the ternary to 'odd' if x % 2 else 'even'", "logic flips — both work"),
        ],
    },
    {
        "slug": "py-classes",
        "category": "Python",
        "title": "Classes — __init__, self, methods",
        "language": "python",
        "summary": "Blueprints for objects. __init__ runs on creation. self is the instance. Methods are functions in the class.",
        "starter_code": "class Dog:\n    # Class attribute (shared by all instances)\n    species = 'Canis familiaris'\n\n    def __init__(self, name, age):\n        # Instance attributes (per-dog)\n        self.name = name\n        self.age = age\n        self.tricks = []  # always a NEW list per instance\n\n    def add_trick(self, trick):\n        self.tricks.append(trick)\n\n    def bark(self):\n        return f'{self.name} says Woof!'\n\n    def __str__(self):\n        return f'Dog({self.name}, {self.age} years old)'\n\n# Create instances\nbuddy = Dog('Buddy', 3)\nmiles = Dog('Miles', 5)\n\nprint(buddy.bark())\nprint(miles.bark())\n\nbuddy.add_trick('sit')\nbuddy.add_trick('roll over')\nprint(f'{buddy.name} knows: {buddy.tricks}')\nprint(f'{miles.name} knows: {miles.tricks}')  # empty — separate list per dog\n\nprint('species:', buddy.species)  # class attribute\nprint(str(buddy))",
        "html_template": "",
        "explanation": (
            "class ClassName: defines the blueprint. __init__ is the constructor — runs when you call ClassName(...). "
            "self is the instance being created (like 'this' in JS). Always the first parameter of methods. "
            "Instance attributes (self.name) — unique per instance. "
            "Class attributes (species) — shared by all instances, lives on the class. "
            "Methods are functions defined in the class body. First param is always self. "
            "__str__ defines what str(instance) returns — used by print(). "
            "Mutable class attributes (like a list) are a footgun — all instances SHARE the same list. "
            "Fix: put mutables in __init__ as instance attributes."
        ),
        "try_changes": [
            ("Add a third dog: rex = Dog('Rex', 2)", "new instance with its own attributes"),
            ("Add a method age_in_dog_years(self): return self.age * 7", "call it as buddy.age_in_dog_years()"),
            ("Change species to 'Canis lupus'", "both dogs' species changes (class attribute)"),
            ("Add a class method @classmethod\\n    def from_dict(cls, d):\\n        return cls(d['name'], d['age'])", "alternative constructor: Dog.from_dict({'name': 'Buddy', 'age': 3})"),
        ],
    },
    {
        "slug": "py-exceptions",
        "category": "Python",
        "title": "try / except / finally",
        "language": "python",
        "summary": "Errors are raised, caught, handled. Don't swallow exceptions silently — at least log them.",
        "starter_code": "def divide(a, b):\n    try:\n        result = a / b\n    except ZeroDivisionError as e:\n        print(f'  cannot divide by zero: {e}')\n        result = None\n    except TypeError as e:\n        print(f'  wrong type: {e}')\n        result = None\n    else:\n        # runs ONLY if no exception was raised\n        print(f'  {a} / {b} = {result}')\n    finally:\n        # ALWAYS runs — even if exception was raised\n        print('  (divide() called)')\n    return result\n\nprint('Test 1: divide(10, 2)')\ndivide(10, 2)\n\nprint('\\nTest 2: divide(10, 0)')\ndivide(10, 0)\n\nprint('\\nTest 3: divide(10, \"two\")')\ndivide(10, 'two')\n\n# Raising your own exceptions\ndef check_age(age):\n    if age < 0:\n        raise ValueError(f'age cannot be negative, got {age}')\n    return age\n\ntry:\n    check_age(-5)\nexcept ValueError as e:\n    print(f'\\nCaught: {type(e).__name__}: {e}')",
        "html_template": "",
        "explanation": (
            "try: runs code that might fail. except: catches specific exception types. "
            "else: runs only if NO exception was raised (rare but useful). "
            "finally: ALWAYS runs, even on exception — use for cleanup (closing files, releasing locks). "
            "Catch SPECIFIC exceptions (except ValueError), not bare except: (catches everything including KeyboardInterrupt). "
            "raise ValueError('message') throws an exception. raise by itself re-raises the current one. "
            "Common exceptions: ValueError, TypeError, KeyError, IndexError, FileNotFoundError, AttributeError. "
            "You can create custom exceptions: class MyError(Exception): pass."
        ),
        "try_changes": [
            ("Change divide(10, 0) to divide(10, 5)", "no ZeroDivisionError"),
            ("Remove the 'as e' from except ZeroDivisionError:", "still works but you can't print the message"),
            ("Add except Exception: print('unknown error') at the end", "catches any other exception"),
            ("Change raise ValueError to raise RuntimeError", "different exception type caught (or not)"),
        ],
    },
    {
        "slug": "py-strings",
        "category": "Python",
        "title": "Strings — f-strings, methods, slicing",
        "language": "python",
        "summary": "Strings are immutable sequences of characters. f-strings are the modern way to format them.",
        "starter_code": "# f-strings (Python 3.6+)\nname = 'Ada'\nage = 36\nprint(f'{name} is {age} years old')\nprint(f'{name!r}')  # repr — shows quotes\nprint(f'{age:>5}')  # right-align in 5 chars\nprint(f'{age:05d}')  # pad with zeros: 00036\nprint(f'{3.14159:.2f}')  # 2 decimal places: 3.14\n\n# Methods\ns = '  Hello, World!  '\nprint(f'strip: \"{s.strip()}\"')\nprint(f'lower: \"{s.lower()}\"')\nprint(f'upper: \"{s.upper()}\"')\nprint(f'replace: \"{s.replace(\"World\", \"Python\")}\"')\nprint(f'split: {s.strip().split(\", \")}')  # ['Hello', 'World!']\nprint(f'startswith: {s.strip().startswith(\"Hello\")}')\n\n# Slicing (same as lists)\nword = 'Python'\nprint(f'first 3: {word[:3]}')     # 'Pyt'\nprint(f'last 3: {word[-3:]}')     # 'hon'\nprint(f'reversed: {word[::-1]}')  # 'nohtyP'\nprint(f'every other: {word[::2]}')  # 'Pto'\n\n# Join (opposite of split)\nwords = ['Hello', 'World']\nprint(' '.join(words))  # 'Hello World'\nprint('-'.join(words))  # 'Hello-World'",
        "html_template": "",
        "explanation": (
            "f'...' strings evaluate {expressions} inside. Format spec after colon: {value:format}. "
            "  !r — use repr() (shows quotes around strings). "
            "  >5 — right-align in 5 chars. <5 — left-align. ^5 — center. "
            "  05d — pad with zeros to width 5. .2f — float with 2 decimals. , — thousands separator. "
            "Strings are IMMUTABLE — every method returns a NEW string, never modifies the original. "
            "Common methods: strip, lower, upper, replace, split, join, startswith, endswith, find, count. "
            "split(sep) breaks into a list. join(list) glues a list into a string — they're inverses."
        ),
        "try_changes": [
            ("Change {age:>5} to {age:<5}", "left-align instead of right"),
            ("Change {age:05d} to {age:+d}", "shows + sign for positive numbers"),
            ("Change {3.14159:.2f} to {3.14159:.4f}", "4 decimal places"),
            ("Add a thousand separator: f'{1234567:,}'", "1,234,567"),
            ("Change s.strip().split(', ') to s.strip().split()", "splits on any whitespace"),
        ],
    },
    {
        "slug": "py-comprehensions",
        "category": "Python",
        "title": "Comprehensions — list, dict, set, generator",
        "language": "python",
        "summary": "One-line loops that build collections. Faster and more Pythonic than for+append.",
        "starter_code": "# List comprehension\nsquares = [x*x for x in range(5)]\nprint('squares:', squares)\n\n# With filter\nevens = [x for x in range(10) if x % 2 == 0]\nprint('evens:', evens)\n\n# With if/else (different from filter!)\nlabels = ['even' if x % 2 == 0 else 'odd' for x in range(5)]\nprint('labels:', labels)\n\n# Dict comprehension\nsquare_dict = {x: x*x for x in range(5)}\nprint('square_dict:', square_dict)\n\n# Set comprehension\nunique_lens = {len(w) for w in ['a', 'bb', 'ccc', 'bb', 'a']}\nprint('unique_lens:', unique_lens)\n\n# Generator expression (lazy — uses () not [])\ngen = (x*x for x in range(5))\nprint('gen:', gen)  # generator object\nprint('list(gen):', list(gen))  # consume it\n\n# Nested comprehension (matrix transpose)\nmatrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]\ntransposed = [[row[i] for row in matrix] for i in range(3)]\nprint('transposed:', transposed)",
        "html_template": "",
        "explanation": (
            "[expr for x in iter if cond] — list comprehension. The if is a FILTER (skips items where cond is False). "
            "[a if cond else b for x in iter] — if/else EXPRESSION (maps each item to a or b). Different syntax! "
            "{k: v for k, v in iter} — dict comprehension. "
            "{x for x in iter} — set comprehension (deduplicates). "
            "(expr for x in iter) — generator expression. Lazy — produces values on demand. Memory-efficient for big data. "
            "Comprehensions are FASTER than for+append because the loop runs in C, not Python. "
            "Don't overdo it — if your comprehension is more than 1 line, use a regular for loop for readability."
        ),
        "try_changes": [
            ("Change [x*x for x in range(5)] to [x*x for x in range(5) if x % 2 == 0]", "only squares of evens: [0, 4, 16]"),
            ("Change the if/else to 'positive' if x > 0 else 'zero' if x == 0 else 'negative'", "nested ternary (hard to read — use a function)"),
            ("Change square_dict to {x: x*x for x in range(10) if x % 2 == 0}", "only even keys"),
            ("Change the generator to a list: list(x*x for x in range(5))", "same as list comprehension"),
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  FASTAPI LABS
# ═══════════════════════════════════════════════════════════════════════════

_FASTAPI_LABS = [
    {
        "slug": "fastapi-first-route",
        "category": "FastAPI",
        "title": "Your first route — @app.get('/path')",
        "language": "fastapi",
        "summary": "A route is a function FastAPI calls when a matching HTTP request arrives. Decorator specifies method + path.",
        "starter_code": "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/')\nasync def root():\n    return {'message': 'Hello, World!'}\n\n@app.get('/health')\nasync def health():\n    return {'status': 'ok'}\n\n@app.get('/users/{user_id}')\nasync def get_user(user_id: int):\n    return {'user_id': user_id, 'name': f'User {user_id}'}\n\n# Run: uvicorn main:app --reload\n# Visit http://localhost:8000/        -> {'message': 'Hello, World!'}\n# Visit http://localhost:8000/health   -> {'status': 'ok'}\n# Visit http://localhost:8000/users/42 -> {'user_id': 42, 'name': 'User 42'}\n# Visit http://localhost:8000/docs     -> auto-generated API docs!",
        "html_template": "",
        "explanation": (
            "@app.get('/path') registers the function below as the handler for GET requests to /path. "
            "Other decorators: @app.post, @app.put, @app.delete, @app.patch. "
            "async def — the function can await I/O. If you have no awaits, regular def works too (FastAPI runs it in a threadpool). "
            "Returning a dict — FastAPI auto-converts to JSON. "
            "{user_id} in the path is a PATH PARAMETER — FastAPI extracts it and passes as a function arg. "
            "The type hint (int) VALIDATES the input — /users/abc returns 422 automatically. "
            "/docs is auto-generated Swagger UI — every FastAPI app gets it for free."
        ),
        "try_changes": [
            ("Change '/' to '/home'", "root is now at /home instead of /"),
            ("Change user_id: int to user_id: str", "/users/abc now works (no validation)"),
            ("Add a new route @app.get('/about') that returns {'app': 'My API'}", "new endpoint"),
            ("Change the return of /health to {'status': 'ok', 'uptime': 100}", "more fields in response"),
        ],
    },
    {
        "slug": "fastapi-path-params",
        "category": "FastAPI",
        "title": "Path parameters — {id} becomes a function arg",
        "language": "fastapi",
        "summary": "Wrap a segment of the path in {braces} and FastAPI extracts it. Type hints validate.",
        "starter_code": "from fastapi import FastAPI, HTTPException\n\napp = FastAPI()\n\n# Path param with int validation\n@app.get('/items/{item_id}')\nasync def get_item(item_id: int):\n    return {'item_id': item_id}\n\n# Multiple path params\n@app.get('/users/{user_id}/posts/{post_id}')\nasync def get_post(user_id: int, post_id: int):\n    return {'user_id': user_id, 'post_id': post_id}\n\n# Path param with str (no validation — accepts anything)\n@app.get('/search/{query}')\nasync def search(query: str):\n    return {'query': query, 'results': []}\n\n# Path param with enum-like choices\nfrom enum import Enum\nclass Color(str, Enum):\n    red = 'red'\n    green = 'green'\n    blue = 'blue'\n\n@app.get('/colors/{color}')\nasync def get_color(color: Color):\n    return {'color': color, 'value': color.value}\n\n# 404 if item doesn't exist\nfake_db = {1: 'apple', 2: 'banana'}\n@app.get('/fruits/{fruit_id}')\nasync def get_fruit(fruit_id: int):\n    if fruit_id not in fake_db:\n        raise HTTPException(status_code=404, detail='Fruit not found')\n    return {'fruit_id': fruit_id, 'name': fake_db[fruit_id]}",
        "html_template": "",
        "explanation": (
            "{param} in path → param becomes a function arg. Type hints validate: "
            "  int — /items/abc returns 422. "
            "  str — anything works. "
            "  float — /items/1.5 works. "
            "  bool — /items/true, /items/1, /items/True work. "
            "  UUID — /items/123e4567-e89b-12d3-a456-426614174000. "
            "Enum types constrain choices — invalid values return 422. "
            "Order matters: /users/me should be defined BEFORE /users/{user_id} (else 'me' is caught by the param route). "
            "HTTPException(status_code, detail) raises an HTTP error with a custom message."
        ),
        "try_changes": [
            ("Change item_id: int to item_id: str", "/items/abc now works"),
            ("Add a new route /products/{product_id} that returns a fake product", "new endpoint"),
            ("Change the Color enum to add 'yellow'", "/colors/yellow works"),
            ("Change HTTPException status_code to 400", "Bad Request instead of Not Found"),
        ],
    },
    {
        "slug": "fastapi-query-params",
        "category": "FastAPI",
        "title": "Query params — ?key=value after the path",
        "language": "fastapi",
        "summary": "Function args that AREN'T path params become query params. Optional with defaults.",
        "starter_code": "from fastapi import FastAPI\n\napp = FastAPI()\n\nfake_items = [{'id': i, 'name': f'item{i}'} for i in range(100)]\n\n# Query params with defaults\n@app.get('/items')\nasync def list_items(skip: int = 0, limit: int = 10):\n    # /items                  -> skip=0, limit=10\n    # /items?skip=20          -> skip=20, limit=10\n    # /items?skip=20&limit=5  -> skip=20, limit=5\n    return fake_items[skip:skip + limit]\n\n# Mixed path + query\n@app.get('/users/{user_id}/items')\nasync def user_items(user_id: int, skip: int = 0, limit: int = 10):\n    return {'user_id': user_id, 'skip': skip, 'limit': limit}\n\n# Optional query param (Optional[int] = None)\nfrom typing import Optional\n@app.get('/search')\nasync def search(q: Optional[str] = None, category: Optional[str] = None):\n    if q is None:\n        return {'message': 'Pass ?q=keyword to search'}\n    return {'query': q, 'category': category}\n\n# Boolean query param\n@app.get('/flags')\nasync def flags(verbose: bool = False):\n    return {'verbose': verbose}\n# /flags            -> verbose=False\n# /flags?verbose=true  -> verbose=True\n# /flags?verbose=1     -> verbose=True (multiple truthy values)",
        "html_template": "",
        "explanation": (
            "Function args that aren't path params are auto-treated as query params. "
            "Arg with default (limit: int = 10) — optional. "
            "Arg without default (q: str) — required. "
            "Optional[T] = None — explicitly optional, defaults to None. "
            "bool params accept: true/false, 1/0, yes/no, on/off (case-insensitive). "
            "Query params appear after ? in URL, separated by &: ?a=1&b=2&c=3. "
            "Great for pagination (skip/limit), filters (category), feature flags (verbose)."
        ),
        "try_changes": [
            ("Change limit: int = 10 to limit: int = 5", "fewer items per page"),
            ("Add a new query param sort: str = 'asc'", "/items?sort=desc"),
            ("Change verbose: bool = False to verbose: bool = True", "default flips"),
            ("Add a required query param by removing the default: q: str", "/items?q=... is required, returns 422 if missing"),
        ],
    },
    {
        "slug": "fastapi-pydantic",
        "category": "FastAPI",
        "title": "Pydantic request bodies — automatic validation",
        "language": "fastapi",
        "summary": "Define a Pydantic model with typed fields. FastAPI validates the JSON body, returns 422 if invalid.",
        "starter_code": "from fastapi import FastAPI\nfrom pydantic import BaseModel, Field, EmailStr\nfrom typing import Optional\nfrom datetime import datetime\n\napp = FastAPI()\n\nclass UserCreate(BaseModel):\n    username: str = Field(..., min_length=3, max_length=20)\n    email: EmailStr\n    age: int = Field(..., ge=0, le=150)\n    bio: Optional[str] = Field(None, max_length=500)\n    is_active: bool = True\n    created_at: datetime = Field(default_factory=datetime.utcnow)\n\n@app.post('/users')\nasync def create_user(user: UserCreate):\n    # FastAPI has ALREADY validated the body before this runs.\n    # If validation fails, it returns 422 without touching your code.\n    return {\n        'id': 1,\n        'username': user.username,\n        'email': user.email,\n        'age': user.age,\n        'is_active': user.is_active,\n    }\n\n# Try with curl:\n# curl -X POST http://localhost:8000/users \\\n#   -H 'Content-Type: application/json' \\\n#   -d '{\"username\":\"ada\",\"email\":\"ada@x.com\",\"age\":36}'\n# -> 200, returns the user dict\n#\n# Validation failures (each returns 422):\n# {\"username\":\"ab\"}            -> min_length=3 violated\n# {\"username\":\"ada\",\"email\":\"not-an-email\"} -> invalid email\n# {\"age\": 200}                  -> le=150 violated\n# {\"username\":\"ada\"}            -> email + age required\n\n# Response model — validates the OUTPUT too\nclass UserResponse(BaseModel):\n    id: int\n    username: str\n    email: EmailStr\n\n@app.post('/users2', response_model=UserResponse)\nasync def create_user2(user: UserCreate):\n    return {'id': 1, **user.model_dump(), 'extra_field': 'ignored'}\n    # response_model strips extra_field automatically",
        "html_template": "",
        "explanation": (
            "Pydantic BaseModel defines the SHAPE of the JSON body. "
            "Field(...) — required. Field(default) — optional with default. "
            "Constraints: min_length, max_length, ge (>=), le (<=), gt (>), lt (<), regex. "
            "Special types: EmailStr, HttpUrl, IPvAnyAddress, conint(ge=0, le=100). "
            "Optional[T] = None — explicitly optional, defaults to None. "
            "Type hints VALIDATE: wrong type → 422 with detailed error pointing at the field. "
            "response_model on the route validates the OUTPUT too — strips extra fields, validates types. "
            "user.model_dump() converts Pydantic model → dict (v2). In v1 it was .dict(). "
            "Benefits: no manual validation, free /docs, type-safe serialization."
        ),
        "try_changes": [
            ("Change min_length=3 to min_length=5", "usernames shorter than 5 chars now 422"),
            ("Add a new field password: str = Field(..., min_length=8)", "password now required"),
            ("Change is_active: bool = True to is_active: bool = False", "default flips"),
            ("Remove the response_model from /users2", "extra_field is now included in the response"),
        ],
    },
    {
        "slug": "fastapi-templates",
        "category": "FastAPI",
        "title": "Jinja2 templates — render HTML on the server",
        "language": "fastapi",
        "summary": "TemplateResponse renders an HTML file with variables. base.html + child.html pattern.",
        "starter_code": "# main.py\nfrom fastapi import FastAPI, Request\nfrom fastapi.responses import HTMLResponse\nfrom fastapi.templating import Jinja2Templates\n\napp = FastAPI()\ntemplates = Jinja2Templates(directory='templates')\n\n@app.get('/', response_class=HTMLResponse)\nasync def home(request: Request):\n    return templates.TemplateResponse('home.html', {\n        'request': request,        # REQUIRED — always pass this\n        'app_name': 'MyAPI',\n        'users': ['Ada', 'Alan', 'Bob'],\n    })\n\n# templates/base.html:\n\"\"\"\n<!DOCTYPE html>\n<html>\n<head>\n  <title>{% block title %}MyApp{% endblock %}</title>\n</head>\n<body>\n  <nav><a href=\"/\">Home</a></nav>\n  <main>{% block content %}{% endblock %}</main>\n</body>\n</html>\n\"\"\"\n\n# templates/home.html:\n\"\"\"\n{% extends 'base.html' %}\n{% block title %}Home — {{ app_name }}{% endblock %}\n{% block content %}\n  <h1>Welcome to {{ app_name }}</h1>\n  <ul>\n    {% for u in users %}\n      <li>{{ u }}</li>\n    {% endfor %}\n  </ul>\n{% endblock %}\n\"\"\"",
        "html_template": "",
        "explanation": (
            "Jinja2Templates(directory='templates') — point at your templates folder. "
            "TemplateResponse(template_name, context_dict) — renders the template with the variables. "
            "'request': request is REQUIRED since FastAPI 0.85 — without it you get an error. "
            "{% extends 'base.html' %} — child template inherits the shell. "
            "{% block name %}...{% endblock %} — named holes the child fills. "
            "{{ variable }} — insert a value. {{ obj.method() }} — call a method. "
            "{% for x in items %}...{% endfor %} — loop. {% if cond %}...{% endif %} — conditional. "
            "{{ x | filter }} — apply a filter (upper, lower, length, default). "
            "Templates run SERVER-SIDE — the browser gets pure HTML. Faster first paint than React."
        ),
        "try_changes": [
            ("Change 'app_name': 'MyAPI' to 'app_name': 'CoolAPI'", "title and h1 change"),
            ("Add a new variable 'count': 100 to the context and show it in home.html", "{{ count }} renders"),
            ("Add a filter: {{ users | length }}", "shows the count"),
            ("Add an if: {% if users %}...{% else %}No users{% endif %}", "conditional rendering"),
        ],
    },
    {
        "slug": "fastapi-dependencies",
        "category": "FastAPI",
        "title": "Dependency injection — Depends()",
        "language": "fastapi",
        "summary": "Share setup/teardown across routes. get_db is the classic example — opens a DB session per request.",
        "starter_code": "from fastapi import FastAPI, Depends, HTTPException\nfrom typing import Optional\n\napp = FastAPI()\n\n# A dependency — a function that yields a value\nfake_db = {'users': [{'id': 1, 'name': 'Ada'}]}\n\ndef get_db():\n    # Setup — runs BEFORE the route\n    print('  [db] opening session')\n    db = fake_db  # in real life: SessionLocal()\n    try:\n        yield db\n        # The route runs here with db injected\n    finally:\n        # Cleanup — runs AFTER the route (even on exception)\n        print('  [db] closing session')\n\n# Use the dependency\n@app.get('/users')\nasync def list_users(db: dict = Depends(get_db)):\n    return db['users']\n\n# Auth dependency — validates a token, returns the user\ndef get_current_user(token: Optional[str] = None):\n    if token != 'secret123':\n        raise HTTPException(status_code=401, detail='Invalid token')\n    return {'id': 1, 'name': 'Ada'}\n\n@app.get('/me')\nasync def me(user: dict = Depends(get_current_user)):\n    # 'token' is automatically parsed from query params by FastAPI\n    return user\n# /me?token=secret123 -> 200, returns Ada\n# /me?token=wrong     -> 401\n# /me                 -> 401\n\n# Dependencies can chain\ndef get_admin(user: dict = Depends(get_current_user)):\n    if user['name'] != 'Ada':\n        raise HTTPException(status_code=403, detail='Admin only')\n    return user\n\n@app.delete('/users/{user_id}')\nasync def delete_user(user_id: int, admin: dict = Depends(get_admin)):\n    return {'deleted': user_id, 'by': admin['name']}",
        "html_template": "",
        "explanation": (
            "Depends(fn) — runs fn before the route, injects the yielded value, runs cleanup after. "
            "The dependency can itself have dependencies (chain). FastAPI builds a DAG. "
            "yield form (gen function) — code before yield is setup, after yield is cleanup. "
            "Cleanup runs EVEN on exception — perfect for closing DB sessions, releasing locks. "
            "Sub-dependencies: get_admin depends on get_current_user — FastAPI resolves in order. "
            "Dependencies can ALSO parse query/cookie/header params (like get_current_user does with token). "
            "Use cases: DB sessions, auth, rate limiting, pagination params, feature flags. "
            "Annotated[type, Depends(...)] (Python 3.9+) is the modern syntax."
        ),
        "try_changes": [
            ("Change 'secret123' to 'mypassword'", "/me?token=mypassword now works"),
            ("Add a new dependency require_admin that checks user['name'] == 'Ada'", "admin-only routes"),
            ("Change get_db's print to a real session: db = SessionLocal()", "real DB session per request"),
            ("Add a query param to get_current_user: from fastapi import Cookie; token: Optional[str] = Cookie(None)", "token now read from cookie instead of query"),
        ],
    },
    {
        "slug": "fastapi-forms",
        "category": "FastAPI",
        "title": "Forms — Form() instead of JSON body",
        "language": "fastapi",
        "summary": "HTML forms send application/x-www-form-urlencoded, not JSON. Use Form(...) to receive.",
        "starter_code": "from fastapi import FastAPI, Form, Request\nfrom fastapi.responses import HTMLResponse, RedirectResponse\nfrom fastapi.templating import Jinja2Templates\n\napp = FastAPI()\ntemplates = Jinja2Templates(directory='templates')\n\n# Show the form\n@app.get('/', response_class=HTMLResponse)\nasync def form(request: Request):\n    return templates.TemplateResponse('form.html', {'request': request})\n\n# Receive the form submission\n@app.post('/submit')\nasync def submit(\n    name: str = Form(...),\n    email: str = Form(...),\n    age: int = Form(...),\n):\n    # Form(...) tells FastAPI to read from form-encoded body, not JSON\n    return {'name': name, 'email': email, 'age': age}\n\n# form.html:\n\"\"\"\n<form method=\"post\" action=\"/submit\">\n  <input type=\"text\" name=\"name\" required>\n  <input type=\"email\" name=\"email\" required>\n  <input type=\"number\" name=\"age\" required>\n  <button type=\"submit\">Submit</button>\n</form>\n\"\"\"\n# NOTE: form enctype defaults to application/x-www-form-urlencoded\n# For file uploads, use enctype=\"multipart/form-data\" + UploadFile = File(...)\n\n# POST /submit with form data:\n# name=Ada&email=ada@x.com&age=36\n# -> 200, returns {'name': 'Ada', 'email': 'ada@x.com', 'age': 36}\n\n# After form submit, redirect to a thank-you page\n@app.post('/submit2')\nasync def submit_and_redirect(\n    name: str = Form(...),\n    email: str = Form(...),\n):\n    # Process the form...\n    print(f'Got: {name} <{email}>')\n    # Redirect to avoid resubmission on refresh\n    return RedirectResponse(url='/thanks', status_code=303)",
        "html_template": "",
        "explanation": (
            "Form(...) — like Body(...) but reads from form-encoded body. "
            "Each Form arg name MUST match the input name='' in HTML. "
            "HTML forms send form-encoded by default (key=value&key=value), not JSON. "
            "For file uploads: <form enctype='multipart/form-data'> + UploadFile = File(...). "
            "PRG pattern (Post/Redirect/Get): after a POST, redirect to a GET page — "
            "prevents the 'Confirm Form Resubmission' browser warning on refresh. "
            "Use status_code=303 (See Other) for the redirect — it's the correct code for PRG."
        ),
        "try_changes": [
            ("Add a new form field: message: str = Form(...)", "add a textarea to the form"),
            ("Change age: int = Form(...) to age: int = Form(0)", "age becomes optional with default 0"),
            ("Change RedirectResponse status_code from 303 to 302", "still works, but 303 is technically correct for PRG"),
            ("Add a checkbox: agree: bool = Form(False)", "checkbox only sends a value when checked"),
        ],
    },
    {
        "slug": "fastapi-static-files",
        "category": "FastAPI",
        "title": "Static files — CSS, JS, images",
        "language": "fastapi",
        "summary": "Mount a directory as a static file server. Files are served as-is, no processing.",
        "starter_code": "from fastapi import FastAPI\nfrom fastapi.staticfiles import StaticFiles\nfrom fastapi.responses import HTMLResponse\nfrom fastapi.templating import Jinja2Templates\n\napp = FastAPI()\n\n# Mount a directory at a URL prefix\n# Files in app/static/ are served at /static/\napp.mount('/static', StaticFiles(directory='app/static'), name='static')\n\ntemplates = Jinja2Templates(directory='app/templates')\n\n@app.get('/', response_class=HTMLResponse)\nasync def home(request):\n    return templates.TemplateResponse('home.html', {'request': request})\n\n# app/templates/home.html:\n\"\"\"\n<!DOCTYPE html>\n<html>\n<head>\n  <link rel=\"stylesheet\" href=\"/static/style.css\">\n</head>\n<body>\n  <h1>Hello</h1>\n  <script src=\"/static/app.js\"></script>\n</body>\n</html>\n\"\"\"\n\n# app/static/style.css:\n\"\"\"\nbody { font-family: sans-serif; margin: 2rem; }\nh1 { color: #a0c000; }\n\"\"\"\n\n# app/static/app.js:\n\"\"\"\nconsole.log('Page loaded');\ndocument.querySelector('h1').addEventListener('click', () => {\n  alert('You clicked the h1!');\n});\n\"\"\"\n\n# Now /static/style.css, /static/app.js are accessible.\n# The browser can fetch them via <link> and <script> tags.",
        "html_template": "",
        "explanation": (
            "app.mount('/prefix', StaticFiles(directory='path'), name='static') — serves every file in 'path' at '/prefix/filename'. "
            "The directory path is RELATIVE TO your CWD when you run uvicorn, not relative to main.py. "
            "name='static' is for URL reversing (rarely used). "
            "Files are served with the correct Content-Type based on extension (.css → text/css, .js → application/javascript). "
            "StaticFiles does NOT do any processing — what's in the file is what's served. "
            "For production: use a CDN or nginx for static files — they're faster than FastAPI. "
            "But for dev, mounting them in FastAPI is fine and convenient."
        ),
        "try_changes": [
            ("Change mount path from '/static' to '/assets'", "URLs change to /assets/style.css"),
            ("Add a new file app/static/logo.png and reference it with <img src=\"/static/logo.png\">", "image appears"),
            ("Change the directory to 'static_files' and create that folder", "files served from new location"),
        ],
    },
    {
        "slug": "fastapi-websocket",
        "category": "FastAPI",
        "title": "WebSocket — real-time bidirectional",
        "language": "fastapi",
        "summary": "Persistent connection. Server can push to client without the client asking. Used for live updates, chat, notifications.",
        "starter_code": "from fastapi import FastAPI, WebSocket, WebSocketDisconnect\nfrom fastapi.responses import HTMLResponse\n\napp = FastAPI()\n\n# In-memory connection manager\nclass ConnectionManager:\n    def __init__(self):\n        self.active: list[WebSocket] = []\n\n    async def connect(self, ws: WebSocket):\n        await ws.accept()\n        self.active.append(ws)\n\n    def disconnect(self, ws: WebSocket):\n        self.active.remove(ws)\n\n    async def broadcast(self, message: str):\n        # Send to EVERY connected client\n        for ws in self.active:\n            await ws.send_text(message)\n\nmanager = ConnectionManager()\n\n@app.websocket('/ws/chat')\nasync def chat_endpoint(ws: WebSocket):\n    await manager.connect(ws)\n    try:\n        while True:\n            # Wait for a message from the client\n            data = await ws.receive_text()\n            # Broadcast to everyone (including sender)\n            await manager.broadcast(f'User: {data}')\n    except WebSocketDisconnect:\n        manager.disconnect(ws)\n        await manager.broadcast('A user left')\n\n# Client-side HTML:\n\"\"\"\n<input id=\"msg\" placeholder=\"Type a message\">\n<button onclick=\"send()\">Send</button>\n<div id=\"chat\"></div>\n\n<script>\n  const ws = new WebSocket('ws://localhost:8000/ws/chat');\n  ws.onmessage = (e) => {\n    document.getElementById('chat').innerHTML += '<p>' + e.data + '</p>';\n  };\n  function send() {\n    ws.send(document.getElementById('msg').value);\n    document.getElementById('msg').value = '';\n  }\n</script>\n\"\"\"",
        "html_template": "",
        "explanation": (
            "@app.websocket('/path') — registers a WebSocket endpoint. "
            "WebSocket is a PERSISTENT connection — unlike HTTP (request → response → close), "
            "WebSocket stays open and EITHER side can send at any time. "
            "await ws.accept() — must be called first to complete the handshake. "
            "await ws.receive_text() / receive_json() / receive_bytes() — block until a message arrives. "
            "await ws.send_text() / send_json() / send_bytes() — send to THIS client. "
            "WebSocketDisconnect exception — raised when the client closes the tab. "
            "ConnectionManager pattern: keep a list of active connections, broadcast to all of them. "
            "Use cases: live leaderboards, chat, notifications, real-time dashboards, multiplayer games. "
            "WebSocket vs polling: WS pushes instantly (0ms lag); polling checks every N seconds (N/2 lag average)."
        ),
        "try_changes": [
            ("Change '/ws/chat' to '/ws/notifications'", "different endpoint URL"),
            ("Change send_text to send_json with {user: 'x', msg: data}", "structured messages"),
            ("Add a 'send_to_sender_only' method that sends only to the originating ws", "private message"),
            ("Add a rate limiter: refuse more than 5 messages per second from one client", "anti-spam"),
        ],
    },
    {
        "slug": "fastapi-middleware",
        "category": "FastAPI",
        "title": "Middleware — runs before/after every request",
        "language": "fastapi",
        "summary": "Wrap the entire app. Each request passes through before reaching the route, response passes through after.",
        "starter_code": "import time\nfrom fastapi import FastAPI, Request\n\napp = FastAPI()\n\n# Timing middleware — adds X-Process-Time header\n@app.middleware('http')\nasync def timing(request: Request, call_next):\n    t0 = time.perf_counter()\n    # call_next runs the actual route handler\n    response = await call_next(request)\n    elapsed_ms = (time.perf_counter() - t0) * 1000\n    response.headers['X-Process-Time'] = f'{elapsed_ms:.1f}ms'\n    return response\n\n# Security headers middleware\n@app.middleware('http')\nasync def security_headers(request: Request, call_next):\n    response = await call_next(request)\n    response.headers['X-Content-Type-Options'] = 'nosniff'\n    response.headers['X-Frame-Options'] = 'DENY'\n    response.headers['X-XSS-Protection'] = '1; mode=block'\n    return response\n\n# Logging middleware\n@app.middleware('http')\nasync def logging_middleware(request: Request, call_next):\n    print(f'-> {request.method} {request.url.path}')\n    response = await call_next(request)\n    print(f'<- {response.status_code}')\n    return response\n\n# Order of execution: LAST added middleware runs FIRST on the way in,\n# LAST on the way out. So for the request above:\n#   -> logging (added last)\n#     -> security_headers\n#       -> timing\n#         -> actual route\n#       <- timing (sets X-Process-Time)\n#     <- security_headers (sets X-Frame-Options)\n#   <- logging (logs status)\n\n@app.get('/')\nasync def root():\n    return {'message': 'Hello'}\n# Response headers include X-Process-Time, X-Frame-Options, X-Content-Type-Options",
        "html_template": "",
        "explanation": (
            "@app.middleware('http') — registers a middleware. Signature: async def(request, call_next). "
            "call_next(request) — runs the next middleware (or the route if you're last). Returns the response. "
            "Code BEFORE call_next runs on the way IN (request). "
            "Code AFTER call_next runs on the way OUT (response). "
            "ORDER: the LAST-added middleware runs FIRST on the request, LAST on the response (onion layers). "
            "Use cases: timing, security headers, CORS, GZip compression, logging, rate limiting, auth checks. "
            "CORS middleware is special — added with app.add_middleware(CORSMiddleware, ...) instead of the decorator. "
            "Middleware runs for EVERY request — keep it fast (no DB queries, no slow I/O)."
        ),
        "try_changes": [
            ("Change the timing log to print only if elapsed > 100ms", "only log slow requests"),
            ("Add a new middleware that sets Cache-Control: no-store", "prevents browser caching"),
            ("Add a middleware that blocks requests with User-Agent containing 'bot'", "anti-bot"),
            ("Change X-Frame-Options from 'DENY' to 'SAMEORIGIN'", "allows framing from same domain"),
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  BENCHMARK ENGINE LABS — how to build a benchmarking engine for ANY model
# ═══════════════════════════════════════════════════════════════════════════

_BENCH_LABS = [
    {
        "slug": "bench-load-pkl-model",
        "category": "Benchmark Engine",
        "title": "Load a .pkl model file (joblib + pickle)",
        "language": "python",
        "summary": "The first step of any benchmarking engine: load the model the user uploaded. joblib.load() and pickle.loads() both work.",
        "starter_code": "import joblib\nimport pickle\nimport io\nimport numpy as np\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.datasets import make_regression\n\n# ── Step 1: Train a dummy model so we have something to save ──\nX, y = make_regression(n_samples=100, n_features=3, noise=5, random_state=42)\nmodel = LinearRegression().fit(X, y)\nprint('Trained:', type(model).__name__)\n\n# ── Step 2: Save it as a .pkl file ──\njoblib.dump(model, 'model.pkl')\nprint('Saved -> model.pkl')\n\n# ── Step 3: Load it back TWO ways ──\n\n# Way 1: joblib.load (preferred for sklearn models)\nmodel_v1 = joblib.load('model.pkl')\nprint('Loaded via joblib:', type(model_v1).__name__)\n\n# Way 2: pickle.loads (works on bytes — what you get from UploadFile.read())\nwith open('model.pkl', 'rb') as f:\n    file_bytes = f.read()\nmodel_v2 = pickle.loads(file_bytes)\nprint('Loaded via pickle.loads:', type(model_v2).__name__)\n\n# ── Step 4: Verify both loaded models predict the same thing ──\nX_new = np.array([[1.5, -0.5, 2.0]])\npred1 = model_v1.predict(X_new)[0]\npred2 = model_v2.predict(X_new)[0]\nprint(f'joblib prediction:  {pred1:.4f}')\nprint(f'pickle prediction:  {pred2:.4f}')\nprint(f'Same? {abs(pred1 - pred2) < 1e-10}')",
        "html_template": "",
        "explanation": (
            "Two ways to load a .pkl model: "
            "joblib.load('model.pkl') — loads from a file path. Faster for numpy arrays. "
            "pickle.loads(bytes) — loads from a bytes object. This is what you use when "
            "the model comes from an HTTP upload: `file_bytes = await upload_file.read()` "
            "then `model = pickle.loads(file_bytes)`. "
            "Both produce the same object — the trained model with all its coefficients. "
            "WARNING: pickle is unsafe for untrusted files — it can execute arbitrary code. "
            "In production, run pickle.loads in a sandbox."
        ),
        "try_changes": [
            ("Change make_regression n_features from 3 to 5", "model trains with 5 features instead of 3"),
            ("Change the save path from 'model.pkl' to 'my_model.pkl'", "saves to a different file"),
            ("Add a print(model.coef_) after loading", "shows the learned coefficients"),
            ("Replace LinearRegression with from sklearn.ensemble import RandomForestRegressor", "different model type — same load code works"),
        ],
    },
    {
        "slug": "bench-run-predict",
        "category": "Benchmark Engine",
        "title": "Run predict() on a loaded model",
        "language": "python",
        "summary": "Once the model is loaded, call .predict(X) to get predictions. This is the core of inference benchmarking.",
        "starter_code": "import joblib\nimport numpy as np\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.datasets import make_regression\nfrom sklearn.model_selection import train_test_split\n\n# Train + save a model (simulating what a user would upload)\nX, y = make_regression(n_samples=200, n_features=4, noise=10, random_state=42)\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\nmodel = LinearRegression().fit(X_train, y_train)\njoblib.dump(model, 'model.pkl')\n\n# ── BENCHMARK ENGINE: load the model + run predictions ──\nloaded_model = joblib.load('model.pkl')\nprint(f'Loaded model: {type(loaded_model).__name__}')\n\n# predict() takes a 2D array — even for a single sample\n# Shape: (n_samples, n_features)\nprint(f'X_test shape: {X_test.shape}')  # (40, 4) — 40 samples, 4 features\n\n# Run predictions on the WHOLE test set\ny_pred = loaded_model.predict(X_test)\nprint(f'y_pred shape: {y_pred.shape}')  # (40,) — 40 predictions\nprint(f'First 5 predictions: {y_pred[:5]}')\nprint(f'First 5 actual:      {y_test[:5]}')\n\n# Predict on a SINGLE new sample (must be 2D!)\nnew_sample = np.array([[1.5, -0.5, 2.0, 0.8]])  # shape (1, 4)\nsingle_pred = loaded_model.predict(new_sample)\nprint(f'\\nSingle sample prediction: {single_pred[0]:.4f}')\n\n# COMMON BUG: passing a 1D array — sklearn will crash or give wrong results\ntry:\n    bad_pred = loaded_model.predict([1.5, -0.5, 2.0, 0.8])  # 1D!\nexcept Exception as e:\n    print(f'\\n1D array error: {type(e).__name__}: {e}')",
        "html_template": "",
        "explanation": (
            "model.predict(X) is the core of inference. "
            "X must be 2D: (n_samples, n_features). Even for 1 sample: shape (1, 4), not (4,). "
            "Returns a 1D array: (n_samples,) — one prediction per input row. "
            "For classification: predict() returns class labels (0, 1, 2...). "
            "predict_proba() returns probabilities (n_samples, n_classes). "
            "The COMMON BUG at the bottom shows what happens with a 1D array — "
            "sklearn either crashes or reshapes it wrong."
        ),
        "try_changes": [
            ("Change test_size from 0.2 to 0.5", "bigger test set → more predictions"),
            ("Replace LinearRegression with RandomForestRegressor(n_estimators=50)", "different model, same predict() call"),
            ("Change new_sample values", "different prediction"),
            ("Add predict_proba (need a classifier): use make_classification instead of make_regression", "returns probabilities instead of values"),
        ],
    },
    {
        "slug": "bench-measure-training-time",
        "category": "Benchmark Engine",
        "title": "Measure training time (time.perf_counter)",
        "language": "python",
        "summary": "The 'benchmark' part: how long does model.fit() take? Use time.perf_counter() for high-precision timing.",
        "starter_code": "import time\nimport numpy as np\nfrom sklearn.linear_model import LinearRegression, Ridge\nfrom sklearn.ensemble import RandomForestRegressor\nfrom sklearn.datasets import make_regression\n\n# Generate a bigger dataset so timing is meaningful\nX, y = make_regression(n_samples=10000, n_features=20, noise=15, random_state=42)\nprint(f'Dataset: {X.shape[0]} samples, {X.shape[1]} features')\n\n# ── Benchmark function: times the fit() call ──\ndef benchmark_training(model, X, y, name):\n    start = time.perf_counter()\n    model.fit(X, y)\n    end = time.perf_counter()\n    elapsed = end - start\n    print(f'  {name:30s}  {elapsed*1000:8.1f} ms')\n    return elapsed\n\nprint('\\nTraining benchmark (3 models):')\nprint('-' * 50)\n\nt1 = benchmark_training(LinearRegression(), X, y, 'LinearRegression')\nt2 = benchmark_training(Ridge(alpha=1.0), X, y, 'Ridge')\nt3 = benchmark_training(RandomForestRegressor(n_estimators=50), X, y, 'RandomForest(50 trees)')\n\nprint('-' * 50)\nprint(f'Fastest: LinearRegression ({t1*1000:.1f} ms)')\nprint(f'Slowest: RandomForest ({t3*1000:.1f} ms)')\nprint(f'RF is {t3/t1:.1f}x slower than LinearRegression')\n\n# ── Why perf_counter not time()? ──\nprint('\\nWhy perf_counter?')\nprint(f'  time.time() resolution:        ~1 ms')\nprint(f'  time.perf_counter() resolution: ~0.001 ms')\nprint(f'  perf_counter is monotonic (never goes backwards)')",
        "html_template": "",
        "explanation": (
            "time.perf_counter() is the right tool for measuring durations. "
            "Higher resolution than time.time() (which is for wall-clock time). "
            "Monotonic — never goes backwards (important on multi-core systems). "
            "The benchmark function wraps fit() with start/end timers. "
            "LinearRegression is fastest (closed-form solution). "
            "RandomForest is slowest (builds 50 trees). "
            "This is what 'benchmarking' means — measuring TIME so you can compare models."
        ),
        "try_changes": [
            ("Change n_samples from 10000 to 100000", "10x more data → all models take longer"),
            ("Change n_estimators from 50 to 200", "RandomForest takes 4x longer"),
            ("Add from sklearn.svm import SVR; benchmark_training(SVR(), X[:1000], y[:1000], 'SVR')", "SVMs are slow on large data"),
            ("Wrap the timing in a loop (run fit 5 times, take average)", "more stable measurement"),
        ],
    },
    {
        "slug": "bench-measure-inference-time",
        "category": "Benchmark Engine",
        "title": "Measure inference time + throughput",
        "language": "python",
        "summary": "How fast can the model make predictions? Measure inference time, per-sample latency, and throughput (samples/sec).",
        "starter_code": "import time\nimport joblib\nimport numpy as np\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.ensemble import RandomForestRegressor\nfrom sklearn.datasets import make_regression\n\n# Generate test data\nX, _ = make_regression(n_samples=10000, n_features=10, noise=10, random_state=42)\nX_test = X[:1000]  # 1000 samples for inference benchmark\nprint(f'Test set: {X_test.shape[0]} samples, {X_test.shape[1]} features')\n\n# Train + save models\nmodels = {\n    'LinearRegression': LinearRegression().fit(X, X[:, 0]),  # dummy target\n    'RandomForest(50)': RandomForestRegressor(n_estimators=50, random_state=42).fit(X, X[:, 0]),\n}\n\n# ── Inference benchmark function ──\ndef benchmark_inference(model, X_test, name):\n    # Warm-up: first predict() call is slower (lazy init)\n    model.predict(X_test[:10])\n\n    # Time the prediction\n    start = time.perf_counter()\n    y_pred = model.predict(X_test)\n    end = time.perf_counter()\n\n    inference_time = end - start\n    n_samples = len(X_test)\n    latency_per_sample = inference_time / n_samples\n    throughput = n_samples / inference_time\n\n    print(f'  {name:25s}  '\n          f'total: {inference_time*1000:7.2f} ms  '\n          f'latency: {latency_per_sample*1e6:7.1f} us/sample  '\n          f'throughput: {throughput:8.0f} samples/sec')\n    return inference_time, throughput\n\nprint('\\nInference benchmark:')\nprint('-' * 80)\nfor name, model in models.items():\n    benchmark_inference(model, X_test, name)\n\n# ── Single-sample latency (what real-time APIs care about) ──\nprint('\\nSingle-sample latency (real-time API scenario):')\nfor name, model in models.items():\n    sample = X_test[:1]  # 1 sample, shape (1, 10)\n    # Average over 100 calls\n    start = time.perf_counter()\n    for _ in range(100):\n        model.predict(sample)\n    end = time.perf_counter()\n    avg_latency_us = (end - start) / 100 * 1e6\n    print(f'  {name:25s}  {avg_latency_us:7.1f} us per prediction')",
        "html_template": "",
        "explanation": (
            "Three metrics matter for inference: "
            "(1) TOTAL inference time — how long for the whole test set. "
            "(2) PER-SAMPLE LATENCY — inference_time / n_samples. What users feel. "
            "(3) THROUGHPUT — n_samples / inference_time. How many requests/sec the model can handle. "
            "WARM-UP is critical: the first predict() call is slower (lazy initialization, JIT compilation). "
            "Always warm up before timing, or your numbers will be skewed. "
            "For real-time APIs, measure SINGLE-SAMPLE latency (predict 1 sample, average over 100 calls). "
            "Batch prediction is always faster per-sample (amortized overhead)."
        ),
        "try_changes": [
            ("Change X_test size from 1000 to 10000", "bigger batch → higher throughput"),
            ("Change n_estimators from 50 to 200", "RandomForest takes longer per prediction"),
            ("Remove the warm-up call", "first prediction will be slower, skewing the average"),
            ("Change the single-sample loop from 100 to 1000 iterations", "more stable average"),
        ],
    },
    {
        "slug": "bench-regression-metrics",
        "category": "Benchmark Engine",
        "title": "Regression metrics — MAE, MSE, RMSE, R²",
        "language": "python",
        "summary": "Compute the 4 standard regression metrics. Each tells you something different about model quality.",
        "starter_code": "import numpy as np\nfrom sklearn.linear_model import LinearRegression, RandomForestRegressor\nfrom sklearn.datasets import make_regression\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score\n\n# Generate data + train 2 models\nX, y = make_regression(n_samples=500, n_features=5, noise=20, random_state=42)\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n\nlr = LinearRegression().fit(X_train, y_train)\nrf = RandomForestRegressor(n_estimators=50, random_state=42).fit(X_train, y_train)\n\n# ── Compute metrics for both models ──\ndef compute_metrics(model, X_test, y_test, name):\n    y_pred = model.predict(X_test)\n\n    mae = mean_absolute_error(y_test, y_pred)\n    mse = mean_squared_error(y_test, y_pred)\n    rmse = np.sqrt(mse)\n    r2 = r2_score(y_test, y_pred)\n\n    print(f'\\n{name}:')\n    print(f'  MAE  = {mae:8.2f}   (avg error — easy to interpret)')\n    print(f'  MSE  = {mse:8.2f}   (squared error — punishes big errors)')\n    print(f'  RMSE = {rmse:8.2f}   (sqrt of MSE — back in original units)')\n    print(f'  R²   = {r2:8.4f}   (0-1, how much better than guessing mean)')\n    return {'MAE': mae, 'MSE': mse, 'RMSE': rmse, 'R2': r2}\n\nlr_metrics = compute_metrics(lr, X_test, y_test, 'LinearRegression')\nrf_metrics = compute_metrics(rf, X_test, y_test, 'RandomForest')\n\n# ── Compare ──\nprint('\\n' + '=' * 50)\nprint('Comparison (lower is better for MAE/MSE/RMSE, higher for R²):')\nfor metric in ['MAE', 'MSE', 'RMSE', 'R2']:\n    lr_val = lr_metrics[metric]\n    rf_val = rf_metrics[metric]\n    if metric == 'R2':\n        winner = 'RF' if rf_val > lr_val else 'LR'\n    else:\n        winner = 'RF' if rf_val < lr_val else 'LR'\n    print(f'  {metric:5s}  LR={lr_val:8.2f}  RF={rf_val:8.2f}  winner: {winner}')",
        "html_template": "",
        "explanation": (
            "4 metrics, 4 questions: "
            "MAE (Mean Absolute Error) — 'on average, how far off?' Same units as target. Most interpretable. "
            "MSE (Mean Squared Error) — squares errors, so big errors count more. Units are target² (hard to interpret). "
            "RMSE (Root Mean Squared Error) — sqrt of MSE. Back in target units. Like MAE but punishes outliers. "
            "R² (R-squared) — 0 to 1. How much better than just predicting the mean. 1=perfect, 0=mean, <0=worse than mean. "
            "Rule of thumb: report MAE to non-technical people, R² in papers, RMSE when comparing models with outliers."
        ),
        "try_changes": [
            ("Change noise from 20 to 50 in make_regression", "harder data → all metrics worse"),
            ("Change n_estimators from 50 to 200", "RF might improve slightly"),
            ("Add from sklearn.svm import SVR; compute SVR metrics", "compare 3 models"),
            ("Change test_size from 0.2 to 0.4", "bigger test set → more stable metrics"),
        ],
    },
    {
        "slug": "bench-classification-metrics",
        "category": "Benchmark Engine",
        "title": "Classification metrics — accuracy, precision, recall, F1",
        "language": "python",
        "summary": "For classification models: accuracy, precision, recall, F1, confusion matrix. Each catches a different kind of failure.",
        "starter_code": "import numpy as np\nfrom sklearn.linear_model import LogisticRegression\nfrom sklearn.ensemble import RandomForestClassifier\nfrom sklearn.datasets import make_classification\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.metrics import (\n    accuracy_score, precision_score, recall_score, f1_score,\n    confusion_matrix, classification_report\n)\n\n# Generate IMBALANCED data (90% class 0, 10% class 1) — common in real life\nX, y = make_classification(\n    n_samples=1000, n_features=10, n_informative=5,\n    n_classes=2, weights=[0.9, 0.1],  # 90% / 10% split\n    random_state=42\n)\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n\nlr = LogisticRegression().fit(X_train, y_train)\nrf = RandomForestClassifier(n_estimators=50, random_state=42).fit(X_train, y_train)\n\n# ── Compute classification metrics ──\ndef compute_cls_metrics(model, X_test, y_test, name):\n    y_pred = model.predict(X_test)\n\n    acc = accuracy_score(y_test, y_pred)\n    prec = precision_score(y_test, y_pred, zero_division=0)\n    rec = recall_score(y_test, y_pred, zero_division=0)\n    f1 = f1_score(y_test, y_pred, zero_division=0)\n    cm = confusion_matrix(y_test, y_pred)\n\n    print(f'\\n{name}:')\n    print(f'  Accuracy  = {acc:.4f}   (overall correctness)')\n    print(f'  Precision = {prec:.4f}   (of predicted positives, how many right?)')\n    print(f'  Recall    = {rec:.4f}   (of actual positives, how many caught?)')\n    print(f'  F1        = {f1:.4f}   (harmonic mean of P + R)')\n    print(f'  Confusion matrix:')\n    print(f'    TN={cm[0,0]:4d}  FP={cm[0,1]:4d}')\n    print(f'    FN={cm[1,0]:4d}  TP={cm[1,1]:4d}')\n\ncompute_cls_metrics(lr, X_test, y_test, 'LogisticRegression')\ncompute_cls_metrics(rf, X_test, y_test, 'RandomForest')\n\n# ── Why accuracy is misleading on imbalanced data ──\nprint('\\n' + '=' * 60)\nprint('Why accuracy is MISLEADING on imbalanced data:')\nprint(f'  Class distribution: {np.bincount(y_test)}')\nprint(f'  If we ALWAYS predict class 0, accuracy = {np.bincount(y_test)[0]/len(y_test):.4f}')\nprint(f'  But recall for class 1 = 0.0000 (we never catch positives!)')\nprint(f'  Use F1 or recall for imbalanced data, NOT accuracy.')",
        "html_template": "",
        "explanation": (
            "4 metrics + 1 matrix: "
            "Accuracy — overall correctness. MISLEADING on imbalanced data (90% class 0 → 90% accuracy by always predicting 0). "
            "Precision — of all predicted positives, how many were actually positive? (spam filter: high precision = few false alarms) "
            "Recall — of all actual positives, how many did we catch? (cancer screening: high recall = few missed cases) "
            "F1 — harmonic mean of precision + recall. Use when you can't pick. "
            "Confusion matrix — 2x2 grid of TN, FP, FN, TP. The ground truth behind all metrics. "
            "ALWAYS look at the confusion matrix + class distribution before trusting accuracy."
        ),
        "try_changes": [
            ("Change weights from [0.9, 0.1] to [0.5, 0.5]", "balanced data → accuracy becomes meaningful"),
            ("Change n_estimators from 50 to 200", "RF might improve recall"),
            ("Add print(classification_report(y_test, rf.predict(X_test)))", "per-class breakdown"),
            ("Change the target to make_classification(n_classes=3, ...)", "multi-class — metrics computed per-class"),
        ],
    },
    {
        "slug": "bench-cross-validation",
        "category": "Benchmark Engine",
        "title": "Cross-validation — more honest than a single split",
        "language": "python",
        "summary": "Single train/test split = lucky or unlucky. 5-fold CV runs 5 different splits and averages — more honest.",
        "starter_code": "import numpy as np\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.ensemble import RandomForestRegressor\nfrom sklearn.datasets import make_regression\nfrom sklearn.model_selection import cross_validate, KFold\n\nX, y = make_regression(n_samples=500, n_features=5, noise=20, random_state=42)\n\n# ── KFold: defines HOW to split ──\ncv = KFold(n_splits=5, shuffle=True, random_state=42)\nprint(f'5-fold CV: data split into 5 pieces, train on 4, test on 1, repeat 5x')\n\n# ── cross_validate: runs the CV + computes metrics ──\n# scoring uses sklearn's internal names. 'neg_' prefix because sklearn MAXIMIZES scores.\nscoring = {\n    'MAE': 'neg_mean_absolute_error',\n    'MSE': 'neg_mean_squared_error',\n    'R2': 'r2',\n}\n\ndef benchmark_cv(model, X, y, name):\n    results = cross_validate(model, X, y, cv=cv, scoring=scoring, return_train_score=False)\n\n    # results['test_MAE'] is an array of 5 values (one per fold)\n    # Negate because sklearn negated them (it maximizes)\n    mae_scores = -results['test_MAE']\n    mse_scores = -results['test_MSE']\n    r2_scores = results['test_R2']\n\n    print(f'\\n{name}:')\n    print(f'  MAE per fold:  {mae_scores.round(2)}')\n    print(f'  MAE mean ± std: {mae_scores.mean():.2f} ± {mae_scores.std():.2f}')\n    print(f'  MSE mean:       {mse_scores.mean():.2f}')\n    print(f'  RMSE mean:      {np.sqrt(mse_scores.mean()):.2f}')\n    print(f'  R² per fold:    {r2_scores.round(4)}')\n    print(f'  R² mean ± std:  {r2_scores.mean():.4f} ± {r2_scores.std():.4f}')\n    return r2_scores.mean()\n\nprint('Cross-validation benchmark:')\nprint('=' * 60)\nlr_r2 = benchmark_cv(LinearRegression(), X, y, 'LinearRegression')\nrf_r2 = benchmark_cv(RandomForestRegressor(n_estimators=50, random_state=42), X, y, 'RandomForest')\n\nprint(f'\\nWinner (higher R²): {\"RandomForest\" if rf_r2 > lr_r2 else \"LinearRegression\"}')",
        "html_template": "",
        "explanation": (
            "Why CV? A single train/test split is one sample from many possible splits. "
            "You might get lucky (easy test set) or unlucky (hard test set). "
            "5-fold CV runs 5 different splits and averages — more honest estimate. "
            "KFold(n_splits=5, shuffle=True) — split into 5 pieces, shuffle first. "
            "cross_validate(model, X, y, cv=cv, scoring=...) — runs the CV, returns a dict of arrays. "
            "Each metric is an array of 5 values (one per fold). Report MEAN ± STD. "
            "Std tells you how stable the model is — high std = sensitive to the data split. "
            "neg_ prefix: sklearn maximizes scores, so errors are negated (maximizing -MAE = minimizing MAE)."
        ),
        "try_changes": [
            ("Change n_splits from 5 to 10", "10-fold CV — more folds, slower, slightly more accurate"),
            ("Change shuffle from True to False", "no shuffling — if data is sorted, CV is biased"),
            ("Change n_estimators from 50 to 200", "RF R² might improve"),
            ("Add return_train_score=True and compare train vs test R²", "if train >> test, model is overfitting"),
        ],
    },
    {
        "slug": "bench-handle-any-model",
        "category": "Benchmark Engine",
        "title": "Handle ANY model type (sklearn, xgboost, custom)",
        "language": "python",
        "summary": "A benchmarking engine must work with ANY .pkl — not just LinearRegression. Use duck typing: check for .predict().",
        "starter_code": "import joblib\nimport numpy as np\nfrom sklearn.linear_model import LinearRegression, LogisticRegression\nfrom sklearn.ensemble import RandomForestRegressor, RandomForestClassifier\nfrom sklearn.svm import SVR\nfrom sklearn.datasets import make_regression, make_classification\nfrom sklearn.model_selection import train_test_split\n\n# ── Train 4 different models + save them ──\n# Regression models\nXr, yr = make_regression(n_samples=200, n_features=5, noise=10, random_state=42)\njoblib.dump(LinearRegression().fit(Xr, yr), 'lr.pkl')\njoblib.dump(RandomForestRegressor(n_estimators=20, random_state=42).fit(Xr, yr), 'rf_reg.pkl')\njoblib.dump(SVR().fit(Xr, yr), 'svr.pkl')\n\n# Classification model\nXc, yc = make_classification(n_samples=200, n_features=5, n_informative=3, random_state=42)\njoblib.dump(LogisticRegression().fit(Xc, yc), 'logreg.pkl')\n\n# ── BENCHMARK ENGINE: load any .pkl + figure out what it is ──\ndef benchmark_any_model(pkl_path, X_test, y_test=None):\n    \"\"\"Load a .pkl model and benchmark it — works with ANY model type.\"\"\"\n    model = joblib.load(pkl_path)\n\n    # Duck typing: check what methods the model has\n    has_predict = hasattr(model, 'predict')\n    has_predict_proba = hasattr(model, 'predict_proba')\n    has_feature_importances = hasattr(model, 'feature_importances_')\n    has_coef = hasattr(model, 'coef_')\n\n    print(f'\\nLoaded {pkl_path}:')\n    print(f'  Type: {type(model).__name__}')\n    print(f'  Module: {type(model).__module__}')\n    print(f'  has predict:            {has_predict}')\n    print(f'  has predict_proba:      {has_predict_proba}')\n    print(f'  has feature_importances: {has_feature_importances}')\n    print(f'  has coef_:              {has_coef}')\n\n    if not has_predict:\n        print('  ERROR: model has no predict() method — not a valid ML model')\n        return None\n\n    # Run prediction\n    y_pred = model.predict(X_test)\n    print(f'  Prediction shape: {y_pred.shape}')\n    print(f'  Prediction dtype: {y_pred.dtype}')\n    print(f'  First 3 predictions: {y_pred[:3]}')\n\n    # Detect regression vs classification\n    # If predictions are floats → regression. If integers → classification.\n    is_regression = y_pred.dtype.kind == 'f'\n    print(f'  Task type: {\"REGRESSION\" if is_regression else \"CLASSIFICATION\"}')\n\n    return model\n\n# Test with all 4 models\nprint('Benchmarking 4 different model types:')\nprint('=' * 60)\nbenchmark_any_model('lr.pkl', Xr[:10])\nbenchmark_any_model('rf_reg.pkl', Xr[:10])\nbenchmark_any_model('svr.pkl', Xr[:10])\nbenchmark_any_model('logreg.pkl', Xc[:10])",
        "html_template": "",
        "explanation": (
            "A benchmarking engine MUST work with any model — not just the ones you trained. "
            "Use DUCK TYPING: check hasattr(model, 'predict') instead of isinstance(model, LinearRegression). "
            "Why? Because xgboost.XGBRegressor, lightgbm.LGBMRegressor, custom classes — all have .predict(). "
            "Don't care WHAT it is, care what it CAN DO. "
            "Detect regression vs classification by checking y_pred.dtype: "
            "  float → regression (predict returns continuous values). "
            "  int → classification (predict returns class labels). "
            "  Also check for predict_proba — only classifiers have it. "
            "feature_importances_ → tree-based models (RF, XGBoost). "
            "coef_ → linear models (LinearRegression, LogisticRegression, SVM). "
            "This is how OpenBenchML handles ANY uploaded .pkl file."
        ),
        "try_changes": [
            ("Add a dummy class with no predict() method and try to benchmark it", "shows the error handling"),
            ("Change the regression detection to also check predict_proba", "classifiers have predict_proba, regressors don't"),
            ("Add from sklearn.cluster import KMeans; joblib.dump(KMeans(n_clusters=3).fit(Xr), 'kmeans.pkl'); benchmark_any_model('kmeans.pkl', Xr[:10])", "KMeans has predict() but it's clustering, not classification"),
            ("Print model.get_params() if the model has it", "shows hyperparameters"),
        ],
    },
    {
        "slug": "bench-fastapi-upload-endpoint",
        "category": "Benchmark Engine",
        "title": "FastAPI endpoint — accept .pkl file upload",
        "language": "fastapi",
        "summary": "The FastAPI route that receives the .pkl file + form fields. Uses UploadFile = File() + Form().",
        "starter_code": "from fastapi import FastAPI, UploadFile, File, Form, HTTPException\nfrom fastapi.responses import JSONResponse\nimport pickle\nimport io\nimport time\nimport pandas as pd\nimport numpy as np\n\napp = FastAPI(title=\"Benchmark Engine\")\n\n@app.post(\"/benchmark\")\nasync def benchmark_model(\n    model_file: UploadFile = File(...),\n    dataset: str = Form(...),\n    framework: str = Form(default=\"sklearn\"),\n):\n    \"\"\"Receive a .pkl model + dataset name, run benchmark, return metrics.\"\"\"\n    # 1. Validate the file is a .pkl\n    if not model_file.filename.endswith(\".pkl\"):\n        raise HTTPException(400, \"File must be a .pkl file\")\n\n    # 2. Read the file bytes (async — streams the file)\n    file_bytes = await model_file.read()\n    print(f\"Received {model_file.filename}: {len(file_bytes)} bytes\")\n\n    # 3. Load the model from bytes (pickle.loads, not pickle.load)\n    try:\n        model = pickle.loads(file_bytes)\n    except Exception as e:\n        raise HTTPException(400, f\"Failed to load model: {e}\")\n\n    # 4. Check it's actually a model (duck typing)\n    if not hasattr(model, \"predict\"):\n        raise HTTPException(400, \"File is not a valid ML model (no predict() method)\")\n\n    # 5. Load the dataset (in real life, pick based on `dataset` param)\n    # For demo: generate fake data\n    from sklearn.datasets import make_regression\n    X, y = make_regression(n_samples=200, n_features=5, noise=10, random_state=42)\n\n    # 6. Run predictions + time it\n    start = time.perf_counter()\n    y_pred = model.predict(X)\n    inference_time = time.perf_counter() - start\n\n    # 7. Compute metrics\n    from sklearn.metrics import mean_absolute_error, r2_score\n    mae = float(mean_absolute_error(y, y_pred))\n    r2 = float(r2_score(y, y_pred))\n\n    # 8. Return benchmark result as JSON\n    return JSONResponse({\n        \"status\": \"success\",\n        \"model_type\": type(model).__name__,\n        \"dataset\": dataset,\n        \"framework\": framework,\n        \"n_samples\": len(X),\n        \"MAE\": mae,\n        \"R2\": r2,\n        \"inference_time_sec\": inference_time,\n        \"throughput_samples_per_sec\": len(X) / inference_time,\n    })\n\n# Test with curl:\n# curl -X POST http://localhost:8000/benchmark \\\n#   -F \"model_file=@model.pkl\" \\\n#   -F \"dataset=house\" \\\n#   -F \"framework=sklearn\"",
        "html_template": "",
        "explanation": (
            "The 8 steps of a benchmark endpoint: "
            "(1) Validate file extension — defend against non-.pkl uploads. "
            "(2) await model_file.read() — streams the file as bytes. Async, doesn't load all at once. "
            "(3) pickle.loads(bytes) — deserialize. NOTE: loads (from bytes), not load (from file). "
            "(4) Duck-type check — hasattr(model, 'predict'). Rejects non-model files. "
            "(5) Load dataset — could be from CSV, DB, or generated. Here we generate fake data. "
            "(6) Time the prediction — perf_counter before/after. "
            "(7) Compute metrics — MAE, R² (add more as needed). "
            "(8) Return JSONResponse — the benchmark result. "
            "Form(...) reads from form-encoded body. File(...) reads from multipart upload. "
            "Both are required by the HTML form's enctype='multipart/form-data'."
        ),
        "try_changes": [
            ("Change the validation to also accept .joblib files", "model_file.filename.endswith(('.pkl', '.joblib'))"),
            ("Add a try/except around model.predict()", "catches models that crash on the dataset"),
            ("Add cross-validation (5-fold) before returning", "more honest metrics"),
            ("Change the response to include a 'model_size_bytes' field", "len(file_bytes)"),
        ],
    },
    {
        "slug": "bench-html-upload-form",
        "category": "Benchmark Engine",
        "title": "HTML form — upload .pkl + select dataset",
        "language": "html",
        "summary": "The form users see. File input + dataset dropdown + framework dropdown. enctype=multipart/form-data is CRITICAL.",
        "starter_code": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>Benchmark Engine</title>\n  <style>\n    body { font-family: sans-serif; max-width: 500px; margin: 2rem auto; padding: 1rem; }\n    .form-group { margin-bottom: 1rem; }\n    label { display: block; font-weight: 600; margin-bottom: 0.3rem; }\n    select, input[type=\"file\"] { width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px; }\n    button { background: #a0c000; color: white; border: none; padding: 0.7rem 1.5rem; border-radius: 4px; cursor: pointer; font-size: 1rem; }\n    button:hover { background: #8aab00; }\n    .hint { font-size: 0.85rem; color: #666; margin-top: 0.3rem; }\n  </style>\n</head>\n<body>\n  <h1>Run Benchmark</h1>\n  <p>Upload a trained .pkl model and select a dataset to benchmark it.</p>\n\n  <!-- enctype is CRITICAL for file uploads! -->\n  <form method=\"post\" action=\"/benchmark\" enctype=\"multipart/form-data\">\n\n    <div class=\"form-group\">\n      <label for=\"model_file\">Upload Model (.pkl)</label>\n      <input type=\"file\" id=\"model_file\" name=\"model_file\" accept=\".pkl,.joblib\" required>\n      <div class=\"hint\">Must be a joblib.dump() or pickle.dump() file.</div>\n    </div>\n\n    <div class=\"form-group\">\n      <label for=\"dataset\">Select Dataset</label>\n      <select id=\"dataset\" name=\"dataset\" required>\n        <option value=\"\">-- Choose --</option>\n        <option value=\"house\">House Prices</option>\n        <option value=\"wine\">Wine Quality</option>\n        <option value=\"iris\">Iris</option>\n        <option value=\"titanic\">Titanic</option>\n      </select>\n    </div>\n\n    <div class=\"form-group\">\n      <label for=\"framework\">Framework</label>\n      <select id=\"framework\" name=\"framework\">\n        <option value=\"sklearn\">scikit-learn</option>\n        <option value=\"xgboost\">XGBoost</option>\n        <option value=\"lightgbm\">LightGBM</option>\n        <option value=\"tensorflow\">TensorFlow</option>\n      </select>\n    </div>\n\n    <button type=\"submit\">Run Benchmark</button>\n  </form>\n</body>\n</html>",
        "html_template": "",
        "explanation": (
            "3 critical things for a file-upload form: "
            "(1) enctype='multipart/form-data' — WITHOUT THIS, the file isn't sent! Default enctype (application/x-www-form-urlencoded) only sends text. "
            "(2) <input type='file' name='model_file'> — the name MUST match the FastAPI parameter (model_file: UploadFile = File()). "
            "(3) method='post' — files can't be sent via GET (URLs have length limits). "
            "accept='.pkl,.joblib' — filters the file picker (cosmetic, doesn't validate server-side). "
            "The FastAPI parameter names (model_file, dataset, framework) must EXACTLY match the HTML name attributes. "
            "Mismatch = 422 Unprocessable Entity."
        ),
        "try_changes": [
            ("Remove enctype=\"multipart/form-data\" from the <form>", "file upload silently fails — FastAPI returns 422"),
            ("Change name=\"model_file\" to name=\"model\"", "FastAPI can't find the parameter — 422"),
            ("Add <input type=\"checkbox\" name=\"cross_validate\" value=\"true\"> Run 5-fold CV", "adds an optional benchmark option"),
            ("Add a progress bar <progress> element", "shows upload progress (needs JS)"),
        ],
    },
    {
        "slug": "bench-full-engine",
        "category": "Benchmark Engine",
        "title": "Full benchmark engine — putting it all together",
        "language": "python",
        "summary": "The complete benchmarking function: load .pkl → detect model type → load dataset → predict → time → metrics → return JSON. This is what OpenBenchML does.",
        "starter_code": "import joblib\nimport pickle\nimport time\nimport numpy as np\nimport pandas as pd\nfrom sklearn.model_selection import train_test_split, cross_validate, KFold\nfrom sklearn.metrics import (\n    mean_absolute_error, mean_squared_error, r2_score,\n    accuracy_score, precision_score, recall_score, f1_score\n)\n\n# ════════════════════════════════════════════════════════════════════\n#  THE COMPLETE BENCHMARK ENGINE FUNCTION\n#  Works with ANY .pkl model — sklearn, xgboost, custom.\n# ════════════════════════════════════════════════════════════════════\n\ndef benchmark_model(model_bytes: bytes, X, y, run_cv: bool = True) -> dict:\n    \"\"\"Benchmark any uploaded .pkl model.\n\n    Args:\n        model_bytes: raw bytes from UploadFile.read()\n        X: features (numpy array or DataFrame)\n        y: target (numpy array or Series)\n        run_cv: whether to run 5-fold cross-validation\n\n    Returns:\n        dict with metrics, timing, model info\n    \"\"\"\n    result = {}\n\n    # ── 1. Load the model ──\n    try:\n        model = pickle.loads(model_bytes)\n    except Exception as e:\n        return {\"status\": \"error\", \"message\": f\"Failed to load model: {e}\"}\n\n    result[\"model_type\"] = type(model).__name__\n    result[\"model_module\"] = type(model).__module__\n\n    # ── 2. Duck-type check ──\n    if not hasattr(model, \"predict\"):\n        return {\"status\": \"error\", \"message\": \"Not a valid ML model (no predict method)\"}\n\n    # ── 3. Split data ──\n    X_train, X_test, y_train, y_test = train_test_split(\n        X, y, test_size=0.2, random_state=42\n    )\n    result[\"train_samples\"] = len(X_train)\n    result[\"test_samples\"] = len(X_test)\n\n    # ── 4. Time the prediction ──\n    start = time.perf_counter()\n    y_pred = model.predict(X_test)\n    inference_time = time.perf_counter() - start\n\n    result[\"inference_time_sec\"] = inference_time\n    result[\"latency_per_sample_sec\"] = inference_time / len(X_test)\n    result[\"throughput_samples_per_sec\"] = len(X_test) / inference_time\n\n    # ── 5. Detect task type (regression vs classification) ──\n    is_regression = y_pred.dtype.kind == \"f\"\n    result[\"task_type\"] = \"regression\" if is_regression else \"classification\"\n\n    # ── 6. Compute metrics ──\n    if is_regression:\n        result[\"MAE\"] = float(mean_absolute_error(y_test, y_pred))\n        result[\"MSE\"] = float(mean_squared_error(y_test, y_pred))\n        result[\"RMSE\"] = float(np.sqrt(result[\"MSE\"]))\n        result[\"R2\"] = float(r2_score(y_test, y_pred))\n    else:\n        result[\"accuracy\"] = float(accuracy_score(y_test, y_pred))\n        result[\"precision\"] = float(precision_score(y_test, y_pred, average=\"weighted\", zero_division=0))\n        result[\"recall\"] = float(recall_score(y_test, y_pred, average=\"weighted\", zero_division=0))\n        result[\"f1\"] = float(f1_score(y_test, y_pred, average=\"weighted\", zero_division=0))\n\n    # ── 7. Cross-validation (optional) ──\n    if run_cv:\n        cv = KFold(n_splits=5, shuffle=True, random_state=42)\n        if is_regression:\n            scoring = {\"MAE\": \"neg_mean_absolute_error\", \"R2\": \"r2\"}\n        else:\n            scoring = {\"accuracy\": \"accuracy\", \"f1\": \"f1_weighted\"}\n\n        try:\n            cv_results = cross_validate(model, X, y, cv=cv, scoring=scoring)\n            for metric in scoring:\n                key = f\"CV_{metric}\"\n                result[key] = float(cv_results[f\"test_{metric}\"].mean())\n        except Exception as e:\n            result[\"cv_error\"] = str(e)\n\n    # ── 8. Feature importances (if available) ──\n    if hasattr(model, \"feature_importances_\"):\n        result[\"feature_importances\"] = model.feature_importances_.tolist()\n    elif hasattr(model, \"coef_\"):\n        result[\"coefficients\"] = np.array(model.coef_).ravel().tolist()\n\n    result[\"status\"] = \"success\"\n    return result\n\n\n# ════════════════════════════════════════════════════════════════════\n#  TEST THE ENGINE WITH 2 DIFFERENT MODEL TYPES\n# ════════════════════════════════════════════════════════════════════\nfrom sklearn.linear_model import LinearRegression, LogisticRegression\nfrom sklearn.ensemble import RandomForestRegressor\nfrom sklearn.datasets import make_regression, make_classification\n\n# Test 1: Regression model\nprint('=' * 60)\nprint('TEST 1: Regression (LinearRegression)')\nprint('=' * 60)\nXr, yr = make_regression(n_samples=500, n_features=5, noise=15, random_state=42)\nlr = LinearRegression().fit(Xr, yr)\nmodel_bytes_r = pickle.dumps(lr)\nresult_r = benchmark_model(model_bytes_r, Xr, yr)\nfor k, v in result_r.items():\n    if isinstance(v, list):\n        print(f'  {k}: [{len(v)} values]')\n    else:\n        print(f'  {k}: {v}')\n\n# Test 2: Classification model\nprint('\\n' + '=' * 60)\nprint('TEST 2: Classification (LogisticRegression)')\nprint('=' * 60)\nXc, yc = make_classification(n_samples=500, n_features=5, n_informative=3, random_state=42)\nclf = LogisticRegression().fit(Xc, yc)\nmodel_bytes_c = pickle.dumps(clf)\nresult_c = benchmark_model(model_bytes_c, Xc, yc)\nfor k, v in result_c.items():\n    if isinstance(v, list):\n        print(f'  {k}: [{len(v)} values]')\n    else:\n        print(f'  {k}: {v}')",
        "html_template": "",
        "explanation": (
            "This is the COMPLETE benchmark engine — exactly what OpenBenchML does. "
            "8 steps: load → validate → split → time → detect type → metrics → CV → importances. "
            "KEY INSIGHT: the function takes model BYTES (not a file path) — that's what you get from UploadFile.read(). "
            "Duck typing throughout: hasattr(model, 'predict'), hasattr(model, 'feature_importances_'). "
            "Works with LinearRegression, RandomForest, XGBoost, LightGBM, ANY model with .predict(). "
            "Auto-detects regression vs classification by checking y_pred.dtype. "
            "Returns a dict that FastAPI can serialize to JSON directly. "
            "The 2 tests at the bottom prove it works with BOTH regression AND classification models — same function, no changes."
        ),
        "try_changes": [
            ("Change CV folds from 5 to 10", "more folds, slower, slightly more accurate"),
            ("Add a 'training_time' field by re-fitting the model + timing it", "measures how long training takes"),
            ("Replace LogisticRegression with RandomForestClassifier", "same function works — that's the point"),
            ("Add error handling for when X has wrong number of features", "model.predict crashes if features don't match"),
        ],
    },
    {
        "slug": "bench-save-and-compare",
        "category": "Benchmark Engine",
        "title": "Save benchmark results + compare models",
        "language": "python",
        "summary": "Run benchmarks on multiple models, save results to a DataFrame, compare side-by-side. This is how leaderboards work.",
        "starter_code": "import pickle\nimport time\nimport numpy as np\nimport pandas as pd\nfrom sklearn.linear_model import LinearRegression, Ridge\nfrom sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor\nfrom sklearn.svm import SVR\nfrom sklearn.datasets import make_regression\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.metrics import mean_absolute_error, r2_score\n\n# Generate data\nX, y = make_regression(n_samples=1000, n_features=10, noise=20, random_state=42)\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\n\n# ── Define models to benchmark ──\nmodels = {\n    'LinearRegression': LinearRegression(),\n    'Ridge': Ridge(alpha=1.0),\n    'RandomForest': RandomForestRegressor(n_estimators=50, random_state=42),\n    'GradientBoosting': GradientBoostingRegressor(n_estimators=50, random_state=42),\n    'SVR': SVR(),\n}\n\n# ── Benchmark function (simplified) ──\ndef benchmark(model, X_train, y_train, X_test, y_test):\n    # Train\n    t0 = time.perf_counter()\n    model.fit(X_train, y_train)\n    train_time = time.perf_counter() - t0\n\n    # Predict\n    t0 = time.perf_counter()\n    y_pred = model.predict(X_test)\n    infer_time = time.perf_counter() - t0\n\n    # Metrics\n    mae = mean_absolute_error(y_test, y_pred)\n    r2 = r2_score(y_test, y_pred)\n\n    return {\n        'train_time_ms': train_time * 1000,\n        'infer_time_ms': infer_time * 1000,\n        'throughput_sps': len(X_test) / infer_time,\n        'MAE': mae,\n        'R2': r2,\n    }\n\n# ── Run benchmark on all models ──\nresults = []\nfor name, model in models.items():\n    print(f'Benchmarking {name}...')\n    metrics = benchmark(model, X_train, y_train, X_test, y_test)\n    metrics['model'] = name\n    results.append(metrics)\n\n# ── Save to DataFrame (this is how leaderboards work) ──\ndf = pd.DataFrame(results).set_index('model')\nprint('\\n' + '=' * 70)\nprint('BENCHMARK RESULTS')\nprint('=' * 70)\nprint(df.round(3).to_string())\n\n# ── Find the winner ──\nbest_r2 = df['R2'].idxmax()\nfastest = df['infer_time_ms'].idxmin()\nprint(f'\\nBest R²:  {best_r2} ({df.loc[best_r2, \"R2\"]:.4f})')\nprint(f'Fastest:  {fastest} ({df.loc[fastest, \"infer_time_ms\"]:.2f} ms)')\n\n# ── Save results to CSV (persist for leaderboard) ──\ndf.to_csv('benchmark_results.csv')\nprint('\\nSaved -> benchmark_results.csv')\n\n# ── Load + display later (simulating a leaderboard) ──\nprint('\\nLeaderboard (sorted by R²):')\nleaderboard = pd.read_csv('benchmark_results.csv').sort_values('R2', ascending=False)\nprint(leaderboard[['model', 'R2', 'MAE', 'infer_time_ms']].round(3).to_string(index=False))",
        "html_template": "",
        "explanation": (
            "This is how a LEADERBOARD works: "
            "(1) Define multiple models to compare. "
            "(2) Benchmark each — train time, inference time, metrics. "
            "(3) Store results in a pandas DataFrame. "
            "(4) Save to CSV (or a database table). "
            "(5) Load + sort by metric to show the leaderboard. "
            "The benchmark function is the SAME for all models — that's the point. "
            "You can add XGBoost, LightGBM, neural nets — same function, same DataFrame, same leaderboard. "
            "In OpenBenchML, the DataFrame is stored in a database (LeaderboardEntry table) and "
            "rendered as an HTML table on the /leaderboard page. WebSocket pushes update it live."
        ),
        "try_changes": [
            ("Add from sklearn.neighbors import KNeighborsRegressor; models['KNN'] = KNeighborsRegressor(n_neighbors=5)", "another model in the comparison"),
            ("Change the sort from R2 to MAE (ascending=True for errors)", "leaderboard sorted by lowest error"),
            ("Add a 'memory_mb' column using psutil.Process().memory_info().rss", "tracks RAM usage per model"),
            ("Wrap the benchmark loop in cross_validate for more honest results", "5-fold CV per model"),
        ],
    },
    {
        "slug": "bench-error-handling",
        "category": "Benchmark Engine",
        "title": "Error handling — when the .pkl is broken or wrong",
        "language": "python",
        "summary": "Real users upload broken files. Your benchmark engine must handle: corrupt .pkl, wrong model type, feature mismatch, predict() crashes.",
        "starter_code": "import pickle\nimport numpy as np\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.datasets import make_regression\n\n# ── A robust benchmark function with full error handling ──\ndef safe_benchmark(model_bytes, X_test, y_test=None):\n    \"\"\"Benchmark a .pkl model with comprehensive error handling.\n\n    Returns dict with 'status' = 'success' or 'error'.\n    Never raises — always returns a dict (safe for FastAPI).\n    \"\"\"\n    result = {\"status\": \"error\"}\n\n    # ── 1. Empty file ──\n    if not model_bytes or len(model_bytes) == 0:\n        result[\"message\"] = \"Empty file — no model data received\"\n        return result\n\n    # ── 2. Too large (> 100 MB) ──\n    if len(model_bytes) > 100 * 1024 * 1024:\n        result[\"message\"] = f\"File too large: {len(model_bytes) / 1e6:.1f} MB (max 100 MB)\"\n        return result\n\n    # ── 3. Not a valid pickle file ──\n    try:\n        model = pickle.loads(model_bytes)\n    except pickle.UnpicklingError as e:\n        result[\"message\"] = f\"Not a valid .pkl file: {e}\"\n        return result\n    except Exception as e:\n        result[\"message\"] = f\"Failed to load model: {type(e).__name__}: {e}\"\n        return result\n\n    result[\"model_type\"] = type(model).__name__\n\n    # ── 4. Not an ML model (no predict method) ──\n    if not hasattr(model, \"predict\"):\n        result[\"message\"] = f\"Loaded object is {type(model).__name__}, not an ML model (no predict method)\"\n        return result\n\n    # ── 5. Feature mismatch (model expects different number of features) ──\n    try:\n        y_pred = model.predict(X_test)\n    except ValueError as e:\n        if \"feature\" in str(e).lower() or \"shape\" in str(e).lower():\n            n_expected = getattr(model, \"n_features_in_\", \"?\")\n            result[\"message\"] = (\n                f\"Feature mismatch: model expects {n_expected} features, \"\n                f\"got {X_test.shape[1]}. Retrain with the correct dataset.\"\n            )\n        else:\n            result[\"message\"] = f\"Prediction failed: {e}\"\n        return result\n    except Exception as e:\n        result[\"message\"] = f\"Prediction failed: {type(e).__name__}: {e}\"\n        return result\n\n    # ── 6. Success — compute metrics if y_test provided ──\n    result[\"status\"] = \"success\"\n    result[\"n_predictions\"] = len(y_pred)\n    result[\"predictions_sample\"] = y_pred[:5].tolist() if hasattr(y_pred, \"tolist\") else list(y_pred[:5])\n\n    if y_test is not None and len(y_test) == len(y_pred):\n        try:\n            from sklearn.metrics import mean_absolute_error, r2_score\n            result[\"MAE\"] = float(mean_absolute_error(y_test, y_pred))\n            result[\"R2\"] = float(r2_score(y_test, y_pred))\n        except Exception as e:\n            result[\"metrics_error\"] = str(e)\n\n    return result\n\n\n# ── TEST: try breaking it in 5 different ways ──\nX, y = make_regression(n_samples=100, n_features=5, noise=10, random_state=42)\ngood_model = LinearRegression().fit(X, y)\n\nprint('Test 1: Valid model')\nr = safe_benchmark(pickle.dumps(good_model), X[:10], y[:10])\nprint(f'  status={r[\"status\"]}, model={r.get(\"model_type\")}, MAE={r.get(\"MAE\")}')\n\nprint('\\nTest 2: Empty file')\nr = safe_benchmark(b\"\", X[:10])\nprint(f'  status={r[\"status\"]}, message={r[\"message\"]}')\n\nprint('\\nTest 3: Not a pickle (random bytes)')\nr = safe_benchmark(b\"this is not a pickle\", X[:10])\nprint(f'  status={r[\"status\"]}, message={r[\"message\"][:60]}...')\n\nprint('\\nTest 4: Valid pickle but not a model (a list)')\nr = safe_benchmark(pickle.dumps([1, 2, 3]), X[:10])\nprint(f'  status={r[\"status\"]}, message={r[\"message\"]}')\n\nprint('\\nTest 5: Feature mismatch (model trained on 5 features, test on 3)')\nwrong_X = X[:10, :3]  # only 3 features instead of 5\nr = safe_benchmark(pickle.dumps(good_model), wrong_X)\nprint(f'  status={r[\"status\"]}, message={r[\"message\"]}')\n\nprint('\\nAll tests passed — engine never crashed!')",
        "html_template": "",
        "explanation": (
            "Production benchmark engines MUST handle broken inputs gracefully. "
            "6 failure modes to handle: "
            "(1) Empty file — user uploaded nothing. "
            "(2) Too large — DoS protection. Cap at 100 MB. "
            "(3) Not a pickle — random bytes, wrong format. "
            "(4) Not a model — valid pickle but it's a list/dict/string, not an ML model. "
            "(5) Feature mismatch — model trained on 5 features, test data has 3. predict() crashes. "
            "(6) Prediction crash — model is broken, predict() raises. "
            "KEY PRINCIPLE: never raise an exception. Always return a dict with status='error' + message. "
            "FastAPI will serialize it to JSON — the user sees a clear error instead of a 500. "
            "The 5 tests at the bottom prove every failure mode is handled."
        ),
        "try_changes": [
            ("Change the size limit from 100 MB to 10 MB", "tighter limit — rejects large models"),
            ("Add a check for pickle's security (only allow certain classes)", "prevents arbitrary code execution"),
            ("Add a timeout: if predict() takes > 10 seconds, kill it", "prevents infinite loops"),
            ("Test with a model that has predict_proba (classifier)", "the function handles it — it just calls predict()"),
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  ML ADVANCED LABS — the THINKING process, not just load+fit
#  Organized by section: Preprocessing → EDA → Maths → Encoding →
#  Imputation → Models → Real-world workflow. For data scientists
#  who already know the basics and want to handle ANY dataset.
# ═══════════════════════════════════════════════════════════════════════════

_ML_ADVANCED_LABS = [
    # ═══════════════ SECTION: PREPROCESSING ═══════════════
    {
        "slug": "ml-preprocessing-thinking",
        "category": "ML Advanced",
        "title": "Preprocessing mindset — the 7 questions to ask ANY dataset",
        "language": "python",
        "summary": "Before touching ML, ask these 7 questions of ANY dataset. This is how senior data scientists think — not 'load + fit'.",
        "starter_code": "import pandas as pd\nimport numpy as np\n\n# ── Load ANY dataset (here we use a synthetic one so it runs) ──\nfrom sklearn.datasets import make_classification\nX, y = make_classification(\n    n_samples=1000, n_features=8, n_informative=5,\n    n_redundant=2, n_classes=3, weights=[0.7, 0.2, 0.1],\n    random_state=42\n)\ndf = pd.DataFrame(X, columns=[f'feature_{i}' for i in range(8)])\ndf['target'] = y\n# Inject some real-world messiness:\ndf.loc[np.random.RandomState(42).randint(0, 1000, 50), 'feature_0'] = np.nan  # nulls\ndf.loc[np.random.RandomState(42).randint(0, 1000, 20), 'feature_1'] = 9999   # outliers\ndf['feature_2'] = df['feature_2'].clip(-2, 2)  # clipped (censored) values\nprint(f'Shape: {df.shape}')\n\n# ════════════════════════════════════════════════════════════════════\n#  THE 7 QUESTIONS — ask these BEFORE any ML\n# ════════════════════════════════════════════════════════════════════\n\n# Q1: How big is it? (rows × cols)\nprint('\\n--- Q1: SIZE ---')\nprint(f'Rows: {len(df):,} | Columns: {df.shape[1]}')\nprint(f'Memory: {df.memory_usage(deep=True).sum() / 1e6:.1f} MB')\n# THINK: <100 rows = too small for ML. >1M rows = need sampling / Dask.\n\n# Q2: What types are the columns? (numeric vs categorical vs datetime)\nprint('\\n--- Q2: TYPES ---')\nprint(df.dtypes.value_counts())\n# THINK: object dtype usually = strings (need encoding). datetime = time features.\n\n# Q3: How many missing values? (and WHERE?)\nprint('\\n--- Q3: MISSING VALUES ---')\nnulls = df.isnull().sum()\nprint(nulls[nulls > 0])\nnull_pct = (nulls[nulls > 0] / len(df) * 100).round(1)\nprint(f'Null %: {dict(null_pct)}')\n# THINK: >50% null = drop the column. 5-50% = impute. <5% = impute or drop rows.\n\n# Q4: Are there outliers? (values way outside the normal range)\nprint('\\n--- Q4: OUTLIERS (using IQR method) ---')\nfor col in df.select_dtypes(include=[np.number]).columns:\n    if col == 'target': continue\n    q1, q3 = df[col].quantile([0.25, 0.75])\n    iqr = q3 - q1\n    lower, upper = q1 - 1.5*iqr, q3 + 1.5*iqr\n    n_outliers = ((df[col] < lower) | (df[col] > upper)).sum()\n    if n_outliers > 0:\n        print(f'  {col}: {n_outliers} outliers (range: [{df[col].min():.2f}, {df[col].max():.2f}])')\n# THINK: outliers might be errors (remove) or real (keep). Domain knowledge matters.\n\n# Q5: Is the target balanced? (classification only)\nprint('\\n--- Q5: TARGET BALANCE ---')\nprint(df['target'].value_counts(normalize=True).round(3))\n# THINK: 90/10 split = imbalanced. Use class_weight, SMOTE, or stratified split.\n\n# Q6: Are there duplicate rows?\nprint('\\n--- Q6: DUPLICATES ---')\nprint(f'Duplicate rows: {df.duplicated().sum()}')\n# THINK: duplicates = data leakage if same row is in train AND test.\n\n# Q7: What do the first 5 rows LOOK like? (the most underrated question)\nprint('\\n--- Q7: HEAD (look at actual values) ---')\nprint(df.head().to_string())\n# THINK: do the values make sense? Is feature_0 an age? A price? A category code?",
        "html_template": "",
        "explanation": (
            "Senior data scientists don't start with model.fit(). They start with QUESTIONS. "
            "7 questions for ANY dataset: "
            "Q1 SIZE — <100 rows = too small. >1M = need sampling. "
            "Q2 TYPES — object dtype = strings = need encoding. "
            "Q3 NULLS — >50% = drop column. 5-50% = impute. <5% = drop rows or impute. "
            "Q4 OUTLIERS — IQR method: anything outside [Q1-1.5*IQR, Q3+1.5*IQR]. Domain knowledge decides keep/remove. "
            "Q5 BALANCE — 90/10 = imbalanced. Use class_weight, SMOTE, or stratified split. "
            "Q6 DUPLICATES — same row in train + test = data leakage = fake accuracy. "
            "Q7 HEAD — the most underrated. Look at actual values. Do they make sense? "
            "This is the difference between a fresher ('load + fit') and a senior ('understand first')."
        ),
        "try_changes": [
            ("Change n_samples from 1000 to 100", "Q1 shows too-small dataset"),
            ("Inject 60% nulls in feature_0: df['feature_0'] = df['feature_0'].where(np.random.rand(len(df)) > 0.6)", "Q3 shows >50% nulls = drop column"),
            ("Make the target super imbalanced: weights=[0.95, 0.04, 0.01]", "Q5 shows severe imbalance"),
            ("Add a categorical column: df['category'] = np.random.choice(['A','B','C'], len(df))", "Q2 shows object dtype"),
        ],
    },
    {
        "slug": "ml-imputation-strategies",
        "category": "ML Advanced",
        "title": "Imputation — when to use mean vs median vs mode vs KNN vs MICE",
        "language": "python",
        "summary": "Missing values are NOT a 'fill with mean' problem. Different imputation strategies for different situations. Know when to use each.",
        "starter_code": "import pandas as pd\nimport numpy as np\nfrom sklearn.experimental import enable_iterative_imputer  # noqa\nfrom sklearn.impute import SimpleImputer, KNNImputer, IterativeImputer\nfrom sklearn.ensemble import RandomForestRegressor\n\n# ── Create a dataset with KNOWN missing patterns ──\nnp.random.seed(42)\nn = 500\ndf = pd.DataFrame({\n    'age': np.random.normal(40, 12, n).clip(18, 80),        # numeric, normal-ish\n    'income': np.random.lognormal(10.5, 0.6, n),             # numeric, SKEWED (long tail)\n    'city': np.random.choice(['NYC', 'LA', 'SF', 'Chicago'], n),  # categorical\n    'credit_score': np.random.normal(680, 80, n).clip(300, 850),  # numeric, bounded\n})\n\n# Inject missing values (different patterns)\ndf.loc[df.sample(50, random_state=42).index, 'age'] = np.nan          # 10% MCAR\ndf.loc[df[df['income'] > 50000].sample(40, random_state=42).index, 'income'] = np.nan  # MNAR (rich hide income)\ndf.loc[df.sample(30, random_state=42).index, 'city'] = np.nan         # 6% categorical\ndf.loc[df.sample(80, random_state=42).index, 'credit_score'] = np.nan  # 16%\n\nprint('Missing values per column:')\nprint(df.isnull().sum())\nprint(f'\\nTotal rows: {len(df)}')\n\n# ════════════════════════════════════════════════════════════════════\n#  5 IMPUTATION STRATEGIES — pick based on the DATA, not habit\n# ════════════════════════════════════════════════════════════════════\n\nprint('\\n' + '='*60)\nprint('STRATEGY 1: Mean imputation (for NORMAL distributions)')\nprint('='*60)\n# GOOD for: age (normal-ish). BAD for: income (skewed — mean pulled by outliers).\nmean_imp = SimpleImputer(strategy='mean')\ndf_mean = df.copy()\ndf_mean['age'] = mean_imp.fit_transform(df[['age']])\nprint(f'  age mean imputed with: {mean_imp.statistics_[0]:.2f}')\nprint(f'  WHY: age is roughly normal, so mean ≈ median ≈ typical value')\n\nprint('\\n' + '='*60)\nprint('STRATEGY 2: Median imputation (for SKEWED distributions)')\nprint('='*60)\n# GOOD for: income (skewed). BAD for: categorical.\nmed_imp = SimpleImputer(strategy='median')\ndf_med = df.copy()\ndf_med['income'] = med_imp.fit_transform(df[['income']])\nprint(f'  income median imputed with: {med_imp.statistics_[0]:.2f}')\nprint(f'  WHY: income is right-skewed (lognormal). Mean is pulled up by billionaires.')\nprint(f'  Median is robust to outliers — better represents the typical person.')\n\nprint('\\n' + '='*60)\nprint('STRATEGY 3: Mode imputation (for CATEGORICAL)')\nprint('='*60)\n# GOOD for: city (categorical). NEVER use mean/median on categories.\nmode_imp = SimpleImputer(strategy='most_frequent')\ndf_mode = df.copy()\ndf_mode['city'] = mode_imp.fit_transform(df[['city']]).ravel()\nprint(f'  city mode imputed with: {mode_imp.statistics_[0]}')\nprint(f'  WHY: categorical has no mean. Most frequent = safest default.')\n\nprint('\\n' + '='*60)\nprint('STRATEGY 4: KNN imputation (uses CORRELATION between features)')\nprint('='*60)\n# GOOD for: when features are correlated. age ~ credit_score ~ income.\n# BAD for: large datasets (slow — O(n²)).\nknn_imp = KNNImputer(n_neighbors=5)\ndf_knn = df.copy()\n# KNN only works on numeric — encode city first or skip it\nnumeric_cols = ['age', 'income', 'credit_score']\ndf_knn[numeric_cols] = knn_imp.fit_transform(df[numeric_cols])\nprint(f'  KNN imputed age, income, credit_score using 5 nearest neighbors')\nprint(f'  WHY: a 25-year-old is more like other 25-year-olds than like the population mean.')\nprint(f'  KNN finds similar rows and uses THEIR values — more accurate than mean.')\n\nprint('\\n' + '='*60)\nprint('STRATEGY 5: MICE / IterativeImputer (models each feature using others)')\nprint('='*60)\n# GOOD for: complex missing patterns. BAD for: speed (trains a model per column).\nmice_imp = IterativeImputer(\n    estimator=RandomForestRegressor(n_estimators=10, random_state=42),\n    max_iter=10, random_state=42\n)\ndf_mice = df.copy()\ndf_mice[numeric_cols] = mice_imp.fit_transform(df[numeric_cols])\nprint(f'  MICE trained a RandomForest to predict each missing value from the others')\nprint(f'  WHY: most sophisticated. Models the RELATIONSHIP between features.')\nprint(f'  E.g., missing income predicted from age + credit_score + city.')\n\n# ════════════════════════════════════════════════════════════════════\n#  COMPARISON — how different are the results?\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('COMPARISON — income imputed values (first 10 nulls):')\nprint('='*60)\nincome_nulls = df['income'].isnull()\nprint(f'  Median:  {df_med.loc[income_nulls, \"income\"].head().values}')\nprint(f'  KNN:     {df_knn.loc[income_nulls, \"income\"].head().values}')\nprint(f'  MICE:    {df_mice.loc[income_nulls, \"income\"].head().values}')",
        "html_template": "",
        "explanation": (
            "5 imputation strategies — pick based on the DATA: "
            "MEAN — for normal distributions (age, height). Pulled by outliers. "
            "MEDIAN — for skewed distributions (income, prices). Robust to outliers. "
            "MODE (most_frequent) — for categorical (city, color). The only option for categories. "
            "KNN — uses correlation. A 25-year-old's missing income = average of 5 similar 25-year-olds. "
            "  More accurate but O(n²) — slow on large data. "
            "MICE (IterativeImputer) — trains a model per column to predict missing values from others. "
            "  Most sophisticated. Best for complex patterns. Slowest. "
            "THREE missingness types you should know: "
            "MCAR (Missing Completely At Random) — safe to impute. "
            "MAR (Missing At Random) — depends on other features (KNN/MICE help). "
            "MNAR (Missing Not At Random) — depends on the missing value itself (rich hide income). Hardest."
        ),
        "try_changes": [
            ("Change income strategy from 'median' to 'mean'", "mean is pulled up by billionaires — bad for skewed data"),
            ("Change KNN n_neighbors from 5 to 20", "more neighbors = smoother but less specific imputation"),
            ("Add a constant imputer: SimpleImputer(strategy='constant', fill_value=-999)", "marks missing as a separate value (good for tree models)"),
            ("Add strategy='constant' fill_value='Unknown' for city", "treats missing as its own category"),
        ],
    },
    {
        "slug": "ml-encoding-categorical",
        "category": "ML Advanced",
        "title": "Encoding — OneHot vs Label vs Target vs Frequency vs Embedding",
        "language": "python",
        "summary": "Categorical encoding is NOT just pd.get_dummies(). 5 strategies, each for a different situation. Pick wrong = garbage model.",
        "starter_code": "import pandas as pd\nimport numpy as np\nfrom sklearn.preprocessing import OneHotEncoder, LabelEncoder, OrdinalEncoder\nfrom sklearn.model_selection import train_test_split\n\n# ── Dataset with 3 types of categorical columns ──\nnp.random.seed(42)\nn = 1000\ndf = pd.DataFrame({\n    # LOW cardinality (3 values) — OneHot is perfect\n    'color': np.random.choice(['red', 'green', 'blue'], n),\n    # ORDINAL (has natural order) — Label/Ordinal encoding is correct\n    'education': np.random.choice(['High School', 'Bachelor', 'Master', 'PhD'], n),\n    # HIGH cardinality (50 values) — OneHot creates 50 columns (curse of dimensionality)\n    'city': np.random.choice([f'city_{i}' for i in range(50)], n),\n    # TARGET (what we predict)\n    'income': np.random.lognormal(10.5, 0.5, n),\n})\n\nprint('Dataset:')\nprint(df.head())\nprint(f'\\nCardinalities: color={df[\"color\"].nunique()}, education={df[\"education\"].nunique()}, city={df[\"city\"].nunique()}')\n\n# ════════════════════════════════════════════════════════════════════\n#  STRATEGY 1: OneHotEncoder (for LOW cardinality, NOMINAL categories)\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('STRATEGY 1: OneHotEncoder (color — 3 values, no order)')\nprint('='*60)\nohe = OneHotEncoder(drop='first', sparse_output=False)  # drop='first' avoids multicollinearity\ncolor_encoded = ohe.fit_transform(df[['color']])\nprint(f'  Before: 1 column (color)')\nprint(f'  After: {color_encoded.shape[1]} columns: {list(ohe.get_feature_names_out())}')\nprint(f'  WHY: color has no natural order. red=1, blue=2 would imply red < blue.')\nprint(f'  OneHot creates binary columns — no implied order.')\nprint(f'  drop=\"first\" drops one column (redundant) — avoids the dummy variable trap.')\n\n# ════════════════════════════════════════════════════════════════════\n#  STRATEGY 2: OrdinalEncoder (for ORDINAL categories — has natural order)\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('STRATEGY 2: OrdinalEncoder (education — High School < Bachelor < Master < PhD)')\nprint('='*60)\n# MUST specify the order explicitly!\neducation_order = [['High School', 'Bachelor', 'Master', 'PhD']]\noe = OrdinalEncoder(categories=education_order)\nedu_encoded = oe.fit_transform(df[['education']])\nprint(f'  Mapping: High School=0, Bachelor=1, Master=2, PhD=3')\nprint(f'  First 5: {edu_encoded[:5].ravel()}')\nprint(f'  WHY: education HAS order. PhD > Bachelor makes sense.')\nprint(f'  OneHot would lose this order information.')\nprint(f'  WARNING: only use when the order is REAL. Don\\'t use for nominal (color).')\n\n# ════════════════════════════════════════════════════════════════════\n#  STRATEGY 3: Frequency encoding (for HIGH cardinality)\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('STRATEGY 3: Frequency encoding (city — 50 values, too many for OneHot)')\nprint('='*60)\ncity_freq = df['city'].value_counts(normalize=True)\ndf['city_freq'] = df['city'].map(city_freq)\nprint(f'  city_0 appears {city_freq[\"city_0\"]*100:.1f}% of the time → encoded as {city_freq[\"city_0\"]:.4f}')\nprint(f'  city_1 appears {city_freq[\"city_1\"]*100:.1f}% of the time → encoded as {city_freq[\"city_1\"]:.4f}')\nprint(f'  WHY: OneHot would create 50 columns (curse of dimensionality).')\nprint(f'  Frequency encoding = 1 column. Tree models (RF, XGBoost) handle this well.')\nprint(f'  LOSES information: 2 cities with same frequency get the same code.')\n\n# ════════════════════════════════════════════════════════════════════\n#  STRATEGY 4: Target encoding (for HIGH cardinality + when target matters)\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('STRATEGY 4: Target encoding (city → average income per city)')\nprint('='*60)\n# WARNING: must compute on TRAIN only (else data leakage!)\nX_train, X_test, y_train, y_test = train_test_split(df[['city']], df['income'], test_size=0.2, random_state=42)\ntarget_mean = pd.concat([X_train, y_train], axis=1).groupby('city')['income'].mean()\n# Smooth to avoid overfitting on rare cities\noverall_mean = y_train.mean()\ncity_counts = X_train['city'].value_counts()\nsmoothed = (target_mean * city_counts + overall_mean * 10) / (city_counts + 10)\nprint(f'  city_0 mean income: {target_mean[\"city_0\"]:.0f}')\nprint(f'  city_1 mean income: {target_mean[\"city_1\"]:.0f}')\nprint(f'  WHY: encodes city by its PREDICTIVE power.')\nprint(f'  WARNING: HIGH risk of overfitting. Use smoothing + cross-validation.')\nprint(f'  SMOOTHING: (mean * count + global_mean * 10) / (count + 10)')\nprint(f'  Pulls rare cities toward the global mean — prevents overfitting.')\n\n# ════════════════════════════════════════════════════════════════════\n#  STRATEGY 5: Just drop the column (sometimes the best choice)\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('STRATEGY 5: Drop (when cardinality > 95% or column is useless)')\nprint('='*60)\nprint(f'  If city had 950 unique values out of 1000 rows...')\nprint(f'  ...each city appears ~1 time. Encoding is meaningless.')\nprint(f'  Drop the column. ML can\\'t learn from near-unique identifiers.')",
        "html_template": "",
        "explanation": (
            "5 encoding strategies — pick by cardinality + order: "
            "ONEHOT — low cardinality (<10), nominal (no order). drop='first' to avoid multicollinearity. "
            "ORDINAL — when categories HAVE a natural order (Low < Med < High). Specify the order explicitly! "
            "FREQUENCY — high cardinality (10-100). Replace category with its frequency. Good for trees. "
            "TARGET — high cardinality + predictive target. Replace category with mean target. HIGH overfit risk — use smoothing + CV. "
            "DROP — cardinality > 95% (e.g., user_id, email). Useless for ML. "
            "RULE OF THUMB: "
            "  < 10 unique values → OneHot. "
            "  10-100 → Frequency or Target. "
            "  > 100 with predictive power → Target (with smoothing). "
            "  > 95% unique → Drop. "
            "  Has natural order → Ordinal. "
            "Common mistake: using LabelEncoder on nominal data. LabelEncoder implies order (red=0 < blue=1 < green=2) which is FALSE."
        ),
        "try_changes": [
            ("Remove drop='first' from OneHotEncoder", "creates 3 columns instead of 2 — multicollinearity risk for linear models"),
            ("Use OrdinalEncoder WITHOUT specifying categories (default alphabetical)", "Bachelor=0, High School=1, Master=2, PhD=3 — WRONG order!"),
            ("Increase city cardinality to 200: np.random.choice([f'city_{i}' for i in range(200)], n)", "OneHot would create 200 columns — frequency/target encoding better"),
            ("Change smoothing factor from 10 to 100", "more smoothing — rare cities pulled harder toward global mean"),
        ],
    },

    # ═══════════════ SECTION: EDA ═══════════════
    {
        "slug": "ml-eda-thinking",
        "category": "ML Advanced",
        "title": "EDA mindset — 8 questions that reveal what the data is hiding",
        "language": "python",
        "summary": "Exploratory Data Analysis is not 'df.describe()'. It's a systematic investigation. 8 questions that uncover patterns, leaks, and ML-readiness.",
        "starter_code": "import pandas as pd\nimport numpy as np\n\n# ── Create a realistic dataset with HIDDEN issues ──\nnp.random.seed(42)\nn = 1000\ndf = pd.DataFrame({\n    'age': np.random.normal(40, 12, n).clip(18, 80),\n    'income': np.random.lognormal(10.5, 0.6, n),\n    'years_experience': np.random.randint(0, 40, n),\n    'education_years': np.random.choice([12, 14, 16, 18, 20], n),\n    'city': np.random.choice(['NYC', 'LA', 'SF', 'Chicago', 'Boston'], n),\n    'hire_date': pd.date_range('2010-01-01', periods=n, freq='D'),\n    'salary': np.nan,  # will be computed below\n})\n# Salary depends on experience + education (with some noise)\ndf['salary'] = (\n    30000 +\n    df['years_experience'] * 2500 +\n    df['education_years'] * 4000 +\n    np.random.normal(0, 8000, n) +\n    df['city'].map({'NYC': 15000, 'SF': 20000, 'LA': 10000, 'Chicago': 5000, 'Boston': 8000})\n)\n# Inject a LEAK: salary_per_year (derived from salary — would be cheating in ML)\ndf['salary_per_year'] = df['salary'] / df['years_experience'].clip(1)\n# Inject a constant column (useless for ML)\ndf['country'] = 'USA'\n# Inject a duplicate-ish column\ndf[' yrs_exp '] = df['years_experience']  # whitespace in name + duplicate\n\n# ════════════════════════════════════════════════════════════════════\n#  EDA QUESTION 1: What does each column MEAN?\n# ════════════════════════════════════════════════════════════════════\nprint('Q1: COLUMN MEANINGS')\nprint('-' * 50)\nprint(df.columns.tolist())\nprint('  THINK: Do I understand every column? What UNIT is it in?')\nprint('  PROBLEM: \" yrs_exp \" has whitespace — will cause bugs.')\nprint('  ACTION: Strip whitespace: df.columns = df.columns.str.strip()')\ndf.columns = df.columns.str.strip()\n\n# ════════════════════════════════════════════════════════════════════\n#  EDA QUESTION 2: What's the distribution of each numeric column?\n# ════════════════════════════════════════════════════════════════════\nprint('\\nQ2: DISTRIBUTIONS (mean, std, min, max, quartiles)')\nprint('-' * 50)\nprint(df.describe().round(0).to_string())\nprint('  THINK: Is the min/max reasonable? age=18-80 ✓, income min?')\nprint(f'  income min: {df[\"income\"].min():.0f}, max: {df[\"income\"].max():.0f}')\nprint(f'  salary min: {df[\"salary\"].min():.0f}, max: {df[\"salary\"].max():.0f}')\nprint('  THINK: income is lognormal (skewed). salary is roughly normal.')\n\n# ════════════════════════════════════════════════════════════════════\n#  EDA QUESTION 3: Are there CONSTANT or DUPLICATE columns?\n# ════════════════════════════════════════════════════════════════════\nprint('\\nQ3: CONSTANT / DUPLICATE columns')\nprint('-' * 50)\nfor col in df.columns:\n    n_unique = df[col].nunique()\n    if n_unique == 1:\n        print(f'  CONSTANT: {col} (only value: {df[col].iloc[0]}) — useless for ML, drop it')\n# Check for duplicate columns (same values, different names)\nfor i, col1 in enumerate(df.columns):\n    for col2 in df.columns[i+1:]:\n        if df[col1].equals(df[col2]):\n            print(f'  DUPLICATE: {col1} == {col2} — drop one')\nprint('  ACTION: df = df.drop(columns=[\"country\"])')\n\n# ════════════════════════════════════════════════════════════════════\n#  EDA QUESTION 4: What's the CORRELATION between features?\n# ════════════════════════════════════════════════════════════════════\nprint('\\nQ4: CORRELATIONS (which features move together?)')\nprint('-' * 50)\nnumeric_df = df.select_dtypes(include=[np.number])\ncorr = numeric_df.corr()\n# Find high correlations (excluding self-correlation)\nhigh_corr = []\nfor i in range(len(corr.columns)):\n    for j in range(i+1, len(corr.columns)):\n        c = corr.iloc[i, j]\n        if abs(c) > 0.7:\n            high_corr.append((corr.columns[i], corr.columns[j], c))\nfor c1, c2, val in high_corr:\n    print(f'  {c1} ↔ {c2}: {val:.3f}')\nprint('  THINK: years_experience ↔ salary: 0.85 (makes sense — more exp = more pay)')\nprint('  THINK: salary_per_year ↔ salary: high (OBVIOUSLY — it\\'s derived from salary)')\nprint('  ACTION: salary_per_year is a LEAK — drop it before ML.')\n\n# ════════════════════════════════════════════════════════════════════\n#  EDA QUESTION 5: Is there a TIME component? (often overlooked)\n# ════════════════════════════════════════════════════════════════════\nprint('\\nQ5: TIME component')\nprint('-' * 50)\nprint(f'  hire_date range: {df[\"hire_date\"].min()} to {df[\"hire_date\"].max()}')\nprint(f'  THINK: salary might increase over time (inflation, raises).')\nprint(f'  THINK: if train/test split is random, future data leaks into train.')\nprint(f'  ACTION: for time-series, use TimeSeriesSplit, not train_test_split.')\n\n# ════════════════════════════════════════════════════════════════════\n#  EDA QUESTION 6: Are there HIDDEN DATA LEAKS?\n# ════════════════════════════════════════════════════════════════════\nprint('\\nQ6: DATA LEAKS (the #1 ML bug)')\nprint('-' * 50)\nprint('  A leak = feature that won\\'t be available at prediction time.')\nprint('  Examples: salary_per_year (derived from target), post-event features.')\nprint(f'  Found: salary_per_year correlates {corr.loc[\"salary_per_year\", \"salary\"]:.3f} with salary')\nprint(f'  ACTION: drop salary_per_year — it\\'s derived from the target.')\n\n# ════════════════════════════════════════════════════════════════════\n#  EDA QUESTION 7: What's the target distribution?\n# ════════════════════════════════════════════════════════════════════\nprint('\\nQ7: TARGET distribution (salary)')\nprint('-' * 50)\nprint(f'  Mean: {df[\"salary\"].mean():.0f}')\nprint(f'  Median: {df[\"salary\"].median():.0f}')\nprint(f'  Std: {df[\"salary\"].std():.0f}')\nprint(f'  Skew: {df[\"salary\"].skew():.2f} (0=normal, >0=right-skewed)')\nprint('  THINK: if skew > 1, consider log-transforming the target.')\n\n# ════════════════════════════════════════════════════════════════════\n#  EDA QUESTION 8: How does the target vary by CATEGORY?\n# ════════════════════════════════════════════════════════════════════\nprint('\\nQ8: TARGET by CATEGORY (salary by city)')\nprint('-' * 50)\nprint(df.groupby('city')['salary'].agg(['mean', 'median', 'count']).round(0).to_string())\nprint('  THINK: SF has highest mean salary — makes sense (tech hub).')\nprint('  THINK: city is a predictive feature — keep it.')" ,
        "html_template": "",
        "explanation": (
            "EDA = Exploratory Data Analysis. It's NOT just df.describe(). "
            "8 questions that uncover what the data is HIDING: "
            "Q1 MEANINGS — understand every column. Strip whitespace from names. "
            "Q2 DISTRIBUTIONS — is the min/max reasonable? Is it skewed? "
            "Q3 CONSTANTS/DUPLICATES — constant columns are useless. Duplicate columns waste space. "
            "Q4 CORRELATIONS — features that move together. >0.7 = high. One is redundant. "
            "Q5 TIME — is there a date column? Future data leaking into train = fake accuracy. "
            "Q6 LEAKS — the #1 ML bug. Features derived from the target (salary_per_year from salary). "
            "  Will be perfect at training, fail in production. ALWAYS check for these. "
            "Q7 TARGET DISTRIBUTION — skewed target? Log-transform it. "
            "Q8 TARGET BY CATEGORY — does the target vary by category? If yes, the category is predictive. "
            "Senior data scientists spend HOURS on this. Freshers skip to model.fit(). That's why freshers' models fail in production."
        ),
        "try_changes": [
            ("Remove the leak column (df = df.drop(columns=['salary_per_year'])) before Q4", "the leak won't show up in correlations"),
            ("Add a constant column: df['constant_col'] = 42", "Q3 will detect and flag it"),
            ("Make salary highly skewed: df['salary'] = np.exp(df['salary'] / 20000)", "Q7 will show high skew → log-transform needed"),
            ("Add a duplicate column: df['age_dup'] = df['age']", "Q3 will detect the duplicate"),
        ],
    },
    {
        "slug": "ml-eda-visualization",
        "category": "ML Advanced",
        "title": "EDA visualization — 6 plots that tell you everything",
        "language": "python",
        "summary": "Not 'make a chart'. 6 specific plots, each answering a different question. This is how you SEE the data before modeling.",
        "starter_code": "import pandas as pd\nimport numpy as np\nimport matplotlib.pyplot as plt\n\n# ── Setup: dataset with interesting structure ──\nnp.random.seed(42)\nn = 500\ndf = pd.DataFrame({\n    'age': np.random.normal(40, 12, n).clip(18, 80),\n    'income': np.random.lognormal(10.5, 0.6, n),\n    'years_experience': np.random.randint(0, 40, n),\n    'education': np.random.choice(['High School', 'Bachelor', 'Master', 'PhD'], n),\n    'city': np.random.choice(['NYC', 'LA', 'SF', 'Chicago'], n),\n})\ndf['salary'] = (\n    30000 + df['years_experience'] * 2500 + df['education'].map({'High School': 0, 'Bachelor': 4000, 'Master': 8000, 'PhD': 12000})\n    + np.random.normal(0, 8000, n) + df['city'].map({'NYC': 15000, 'SF': 20000, 'LA': 10000, 'Chicago': 5000})\n)\n\n# ════════════════════════════════════════════════════════════════════\n#  PLOT 1: HISTOGRAM — what's the SHAPE of each numeric column?\n# ════════════════════════════════════════════════════════════════════\nfig, axes = plt.subplots(1, 3, figsize=(15, 4))\naxes[0].hist(df['age'], bins=30, edgecolor='black', color='#a0c000')\naxes[0].set_title('Age (normal distribution)')\naxes[0].set_xlabel('Age'); axes[0].set_ylabel('Count')\n\naxes[1].hist(df['income'], bins=30, edgecolor='black', color='#58a6ff')\naxes[1].set_title('Income (RIGHT-SKEWED — lognormal)')\naxes[1].set_xlabel('Income')\n\naxes[2].hist(np.log(df['income']), bins=30, edgecolor='black', color='#bc8cff')  # log transform\naxes[2].set_title('Log(Income) — now normal!')\naxes[2].set_xlabel('Log(Income)')\nplt.tight_layout()\nplt.savefig('plot1_histogram.png', dpi=100, bbox_inches='tight')\nplt.show()\nprint('Plot 1: HISTOGRAM — shows distribution shape')\nprint('  THINK: income is skewed → log-transform makes it normal → ML models work better')\n\n# ════════════════════════════════════════════════════════════════════\n#  PLOT 2: BOX PLOT — outliers + distribution by category\n# ════════════════════════════════════════════════════════════════════\nfig, axes = plt.subplots(1, 2, figsize=(12, 5))\ndf.boxplot(column='salary', by='city', ax=axes[0])\naxes[0].set_title('Salary by City')\naxes[0].set_xlabel('City'); axes[0].set_ylabel('Salary')\n\ndf.boxplot(column='salary', by='education', ax=axes[1])\naxes[1].set_title('Salary by Education')\naxes[1].set_xlabel('Education'); axes[1].set_ylabel('Salary')\nplt.tight_layout()\nplt.savefig('plot2_boxplot.png', dpi=100, bbox_inches='tight')\nplt.show()\nprint('\\nPlot 2: BOX PLOT — outliers (dots) + median + quartiles')\nprint('  THINK: SF has highest median salary. PhD has highest. Outliers above the whiskers.')\n\n# ════════════════════════════════════════════════════════════════════\n#  PLOT 3: SCATTER PLOT — relationship between 2 numeric features\n# ════════════════════════════════════════════════════════════════════\nfig, ax = plt.subplots(figsize=(8, 5))\ncolors = {'NYC': '#a0c000', 'LA': '#58a6ff', 'SF': '#f85149', 'Chicago': '#bc8cff'}\nfor city, color in colors.items():\n    subset = df[df['city'] == city]\n    ax.scatter(subset['years_experience'], subset['salary'], c=color, label=city, alpha=0.6)\nax.set_xlabel('Years of Experience')\nax.set_ylabel('Salary')\nax.set_title('Salary vs Experience (colored by city)')\nax.legend()\nplt.tight_layout()\nplt.savefig('plot3_scatter.png', dpi=100, bbox_inches='tight')\nplt.show()\nprint('\\nPlot 3: SCATTER — relationship between 2 numeric features')\nprint('  THINK: positive linear trend (more experience = higher salary).')\nprint('  THINK: SF cluster is higher than Chicago — city matters.')\n\n# ════════════════════════════════════════════════════════════════════\n#  PLOT 4: CORRELATION HEATMAP — which features move together?\n# ════════════════════════════════════════════════════════════════════\nfig, ax = plt.subplots(figsize=(8, 6))\ncorr = df.select_dtypes(include=[np.number]).corr()\nim = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')\nax.set_xticks(range(len(corr.columns))); ax.set_xticklabels(corr.columns, rotation=45, ha='right')\nax.set_yticks(range(len(corr.columns))); ax.set_yticklabels(corr.columns)\n# Add correlation values in each cell\nfor i in range(len(corr.columns)):\n    for j in range(len(corr.columns)):\n        ax.text(j, i, f'{corr.iloc[i, j]:.2f}', ha='center', va='center', fontsize=8)\nplt.colorbar(im, label='Correlation')\nax.set_title('Correlation Heatmap')\nplt.tight_layout()\nplt.savefig('plot4_heatmap.png', dpi=100, bbox_inches='tight')\nplt.show()\nprint('\\nPlot 4: HEATMAP — correlations at a glance')\nprint('  THINK: dark red = high positive. Dark blue = high negative.')\nprint('  THINK: years_experience ↔ salary is red (0.85) — strong predictor.')\n\n# ════════════════════════════════════════════════════════════════════\n#  PLOT 5: BAR CHART — categorical distribution\n# ════════════════════════════════════════════════════════════════════\nfig, axes = plt.subplots(1, 2, figsize=(12, 4))\ndf['city'].value_counts().plot.bar(ax=axes[0], color='#a0c000')\naxes[0].set_title('Count by City'); axes[0].set_ylabel('Count')\n\ndf.groupby('education')['salary'].mean().plot.bar(ax=axes[1], color='#58a6ff')\naxes[1].set_title('Mean Salary by Education'); axes[1].set_ylabel('Mean Salary')\nplt.tight_layout()\nplt.savefig('plot5_bar.png', dpi=100, bbox_inches='tight')\nplt.show()\nprint('\\nPlot 5: BAR CHART — counts + means per category')\nprint('  THINK: PhD earns the most. Bachelor > High School. Makes sense.')\n\n# ════════════════════════════════════════════════════════════════════\n#  PLOT 6: PAIR PLOT — all pairwise relationships at once\n# ════════════════════════════════════════════════════════════════════\nfrom pandas.plotting import scatter_matrix\nfig, ax = plt.subplots(figsize=(10, 10))\nscatter_matrix(df[['age', 'income', 'years_experience', 'salary']], ax=ax, diagonal='hist', alpha=0.5)\nplt.suptitle('Pair Plot — all pairwise relationships')\nplt.tight_layout()\nplt.savefig('plot6_pairplot.png', dpi=100, bbox_inches='tight')\nplt.show()\nprint('\\nPlot 6: PAIR PLOT — scatter for every pair + histogram on diagonal')\nprint('  THINK: scan for linear patterns (good for linear models).')\nprint('  THINK: scan for non-linear patterns (need tree models or feature engineering).')\nprint('\\n6 plots = complete EDA. You now KNOW your data.')",
        "html_template": "",
        "explanation": (
            "6 plots, 6 questions: "
            "HISTOGRAM — what's the SHAPE? Normal, skewed, bimodal? Skewed → log-transform. "
            "BOX PLOT — outliers + distribution by category. Dots above whiskers = outliers. "
            "SCATTER — relationship between 2 numeric features. Linear? Non-linear? Clustered by category? "
            "HEATMAP — all correlations at once. Red = positive, blue = negative. Dark = strong. "
            "BAR CHART — counts + means per category. Which category is most common? Which has highest target? "
            "PAIR PLOT — scatter for EVERY pair + histograms on diagonal. Slow but reveals everything. "
            "ORDER MATTERS: histogram first (understand each feature alone), then scatter (pairs), then heatmap (all pairs). "
            "Don't skip to modeling until you've made these 6 plots. You'll miss leaks, outliers, and non-linear patterns."
        ),
        "try_changes": [
            ("Change bins=30 to bins=10 in the histogram", "coarser bins — less detail but clearer shape"),
            ("Add a log scale to the income histogram: axes[1].set_yscale('log')", "shows the tail more clearly"),
            ("Color the scatter by education instead of city", "different clustering pattern"),
            ("Add alpha=0.3 to the scatter (more transparent)", "better for dense data — shows overlap"),
        ],
    },

    # ═══════════════ SECTION: MATHS ═══════════════
    {
        "slug": "ml-maths-linear-regression",
        "category": "ML Advanced",
        "title": "Linear Regression maths — the equation behind .fit()",
        "language": "python",
        "summary": "model.fit() is not magic. It solves y = Xβ + ε using least squares. Understand the equation, the cost function, and the geometry.",
        "starter_code": "import numpy as np\nimport matplotlib.pyplot as plt\nfrom sklearn.linear_model import LinearRegression\n\n# ── The equation: y = β₀ + β₁x₁ + β₂x₂ + ... + ε ──\n# β = coefficients (what we learn)\n# ε = error (what we can't explain)\n\n# ── Generate data with KNOWN coefficients ──\nnp.random.seed(42)\nn = 100\nx = np.random.uniform(0, 10, n)\n# TRUE equation: y = 2 + 3x + noise\ntrue_intercept = 2\ntrue_slope = 3\nnoise = np.random.normal(0, 2, n)  # ε\ny = true_intercept + true_slope * x + noise\n\nprint('TRUE equation: y = 2 + 3x + noise')\nprint(f'TRUE coefficients: intercept={true_intercept}, slope={true_slope}')\n\n# ── Fit LinearRegression — it should RECOVER the true coefficients ──\nmodel = LinearRegression()\nmodel.fit(x.reshape(-1, 1), y)\nprint(f'\\nLEARNED coefficients: intercept={model.intercept_:.2f}, slope={model.coef_[0]:.2f}')\nprint(f'Close to true? intercept diff={abs(model.intercept_ - true_intercept):.2f}, slope diff={abs(model.coef_[0] - true_slope):.2f}')\n\n# ════════════════════════════════════════════════════════════════════\n#  THE MATHS: how does .fit() find the coefficients?\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('THE MATHS: Least Squares')\nprint('='*60)\nprint('Goal: find β that minimizes Σ(y_actual - y_predicted)²')\nprint('This is the \"cost function\" or \"loss function\".')\nprint()\nprint('Matrix form: y = Xβ + ε')\nprint('  y = column vector of targets (n×1)')\nprint('  X = matrix of features (n×p) — first column is all 1s for the intercept')\nprint('  β = column vector of coefficients (p×1)')\nprint('  ε = error vector (n×1)')\nprint()\nprint('Solution (the NORMAL EQUATION):')\nprint('  β = (XᵀX)⁻¹Xᵀy')\nprint('  This is what .fit() computes — in one matrix operation.')\n\n# ── Verify by computing β manually ──\nX_matrix = np.column_stack([np.ones(n), x])  # add intercept column\nbeta_manual = np.linalg.inv(X_matrix.T @ X_matrix) @ X_matrix.T @ y\nprint(f'\\nManual computation: β = {beta_manual}')\nprint(f'sklearn:            intercept={model.intercept_:.4f}, slope={model.coef_[0]:.4f}')\nprint('SAME! sklearn just uses a more numerically stable algorithm (SVD).')\n\n# ════════════════════════════════════════════════════════════════════\n#  THE COST FUNCTION — what we're minimizing\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('THE COST FUNCTION: Mean Squared Error')\nprint('='*60)\nprint('MSE(β) = (1/n) * Σ(yᵢ - β₀ - β₁xᵢ)²')\nprint('This is a BOWL shape (convex) — has one minimum.')\nprint('The minimum is where the gradient = 0.')\nprint('Gradient descent: take steps in the -gradient direction.')\n\n# Visualize the cost function for different slopes\nslopes = np.linspace(0, 6, 100)\nmse_values = [np.mean((y - true_intercept - s*x)**2) for s in slopes]\nfig, ax = plt.subplots(figsize=(8, 5))\nax.plot(slopes, mse_values, color='#a0c000', linewidth=2)\nax.axvline(true_slope, color='green', linestyle='--', label=f'True slope={true_slope}')\nax.axvline(model.coef_[0], color='red', linestyle='--', label=f'Learned slope={model.coef_[0]:.2f}')\nax.set_xlabel('Slope (β₁)')\nax.set_ylabel('MSE (cost)')\nax.set_title('Cost Function — the bowl shape')\nax.legend()\nplt.tight_layout()\nplt.savefig('cost_function.png', dpi=100, bbox_inches='tight')\nplt.show()\nprint('\\nThe BOWL shape: minimum at the true slope (3). sklearn found it (2.97).')\n\n# ════════════════════════════════════════════════════════════════════\n#  GEOMETRY — projection onto a column space\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('GEOMETRY: Linear Regression as Projection')\nprint('='*60)\nprint('Think of X as defining a PLANE (column space).')\nprint('y is a point NOT on the plane (because of noise ε).')\nprint('The PREDICTION ŷ = Xβ is the PROJECTION of y onto the plane.')\nprint('The residual (y - ŷ) is perpendicular to the plane.')\nprint('This is why it\\'s called \"least squares\" — minimizes the squared perpendicular distance.')",
        "html_template": "",
        "explanation": (
            "Linear Regression maths: "
            "EQUATION: y = β₀ + β₁x₁ + ... + ε. β are coefficients, ε is error. "
            "COST FUNCTION: MSE = (1/n)Σ(y - ŷ)². Convex bowl shape — one minimum. "
            "SOLUTION (Normal Equation): β = (XᵀX)⁻¹Xᵀy. Closed-form — computed in one matrix op. "
            "  XᵀX is the Gram matrix. Xᵀy is the feature-target correlation. "
            "  Inverse makes it a 'divide'. sklearn uses SVD (more stable than inverse). "
            "GEOMETRY: X defines a plane. y is a point above the plane. ŷ is the projection. "
            "  Residual (y - ŷ) is perpendicular to the plane. Least squares = minimize squared perpendicular distance. "
            "GRADIENT DESCENT (alternative): start at random β, take steps in -gradient direction. "
            "  Used when XᵀX is too big to invert (millions of features). "
            "ASSUMPTIONS (often violated, often don't matter): "
            "  Linearity, independence, homoscedasticity (constant variance), normal residuals. "
            "KEY INSIGHT: .fit() is not magic. It's matrix algebra. Understand it = debug models."
        ),
        "try_changes": [
            ("Increase noise from 2 to 10", "learned coefficients will be further from true — more error"),
            ("Change true_slope from 3 to -2", "negative relationship — cost function still works"),
            ("Add a non-linear term: y = 2 + 3x + 0.5x² + noise", "LinearRegression will underfit — need PolynomialFeatures"),
            ("Compute R² manually: 1 - SS_res/SS_tot", "matches model.score()"),
        ],
    },
    {
        "slug": "ml-maths-gradient-descent",
        "category": "ML Advanced",
        "title": "Gradient Descent — the engine behind neural networks",
        "language": "python",
        "summary": "Most ML models (neural nets, logistic regression, SVMs) use gradient descent, not closed-form solutions. Understand the algorithm.",
        "starter_code": "import numpy as np\nimport matplotlib.pyplot as plt\n\n# ── Gradient Descent: find the minimum of a function by walking downhill ──\n# f(x) = x² — minimum at x=0\n# f'(x) = 2x — gradient points UPHILL. We go in -gradient direction.\n\n# ── Visualize the function ──\nx = np.linspace(-5, 5, 100)\ny = x**2\nfig, axes = plt.subplots(1, 2, figsize=(12, 5))\naxes[0].plot(x, y, color='#a0c000', linewidth=2)\naxes[0].set_xlabel('x'); axes[0].set_ylabel('f(x) = x²')\naxes[0].set_title('Function to minimize')\n\n# ── Run gradient descent ──\ndef gradient_descent(start_x, learning_rate, n_steps):\n    \"\"\"Minimize f(x) = x² using gradient descent.\"\"\"\n    x = start_x\n    history = [x]\n    for step in range(n_steps):\n        # Gradient of x² is 2x\n        gradient = 2 * x\n        # Update: x = x - learning_rate * gradient\n        x = x - learning_rate * gradient\n        history.append(x)\n    return history\n\n# Run with different learning rates\nlr_small = gradient_descent(start_x=4, learning_rate=0.1, n_steps=20)\nlr_good = gradient_descent(start_x=4, learning_rate=0.5, n_steps=20)\nlr_large = gradient_descent(start_x=4, learning_rate=1.1, n_steps=20)\n\naxes[1].plot(lr_small, [x**2 for x in lr_small], 'o-', color='#58a6ff', label='lr=0.1 (slow)')\naxes[1].plot(lr_good, [x**2 for x in lr_good], 'o-', color='#a0c000', label='lr=0.5 (good)')\naxes[1].plot(lr_large, [x**2 for x in lr_large], 'o-', color='#f85149', label='lr=1.1 (DIVERGES)')\naxes[1].set_xlabel('Step'); axes[1].set_ylabel('f(x)')\naxes[1].set_title('Gradient Descent — learning rate matters!')\naxes[1].legend()\nplt.tight_layout()\nplt.savefig('gradient_descent.png', dpi=100, bbox_inches='tight')\nplt.show()\n\nprint('Gradient Descent Results:')\nprint(f'  lr=0.1 (slow):  final x={lr_small[-1]:.4f} (took 20 steps, still not at 0)')\nprint(f'  lr=0.5 (good):  final x={lr_good[-1]:.4f} (reached 0 fast)')\nprint(f'  lr=1.1 (large): final x={lr_large[-1]:.4f} (DIVERGED — bouncing away!)')\n\n# ════════════════════════════════════════════════════════════════════\n#  THE ALGORITHM — step by step\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('THE ALGORITHM')\nprint('='*60)\nprint('1. Initialize parameters randomly: β = random')\nprint('2. Compute gradient: ∇f = ∂f/∂β (points uphill)')\nprint('3. Update: β = β - learning_rate * ∇f (step downhill)')\nprint('4. Repeat until convergence (gradient ≈ 0)')\nprint()\nprint('LEARNING RATE (lr):')\nprint('  Too small: slow convergence (1000s of steps)')\nprint('  Too large: DIVERGES (bounces away from minimum)')\nprint('  Just right: fast convergence (10-100 steps)')\nprint('  Typical values: 0.001, 0.01, 0.1')\n\n# ════════════════════════════════════════════════════════════════════\n#  VARIANTS — SGD, Mini-batch, Adam\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('VARIANTS')\nprint('='*60)\nprint('BATCH GD: use ALL data per step. Accurate gradient, slow per step.')\nprint('STOCHASTIC GD (SGD): use 1 sample per step. Noisy gradient, fast per step.')\nprint('MINI-BATCH GD: use 32-256 samples. Best of both — standard for neural nets.')\nprint('ADAM: adaptive learning rate per parameter. Most popular optimizer.')\nprint('  Combines momentum (smooths gradient) + RMSprop (adapts lr per param).')\nprint('  Default for deep learning. Works well with lr=0.001.')\n\n# ════════════════════════════════════════════════════════════════════\n#  WHY IT MATTERS — which ML models use GD?\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('WHICH MODELS USE GRADIENT DESCENT?')\nprint('='*60)\nprint('LinearRegression: NO — uses closed-form (Normal Equation)')\nprint('LogisticRegression: YES — no closed-form solution')\nprint('Neural Networks: YES — ALWAYS (backpropagation = chain rule + GD)')\nprint('SVM: YES — uses SMO (a variant of GD)')\nprint('XGBoost/LightGBM: YES — gradient boosting = GD on residuals')\nprint('RandomForest: NO — uses greedy tree building')\nprint()\nprint('If you understand GD, you understand 80% of ML training.')",
        "html_template": "",
        "explanation": (
            "Gradient Descent = the engine of modern ML. "
            "ALGORITHM: (1) init β random, (2) compute gradient ∇f (uphill direction), (3) step β -= lr * ∇f, (4) repeat. "
            "LEARNING RATE: too small = slow. Too large = diverge. Just right = fast. "
            "  Start with 0.001, tune by 3x (0.001 → 0.003 → 0.01). "
            "VARIANTS: "
            "  Batch GD — all data per step. Accurate, slow. "
            "  SGD — 1 sample per step. Noisy, fast. "
            "  Mini-batch (32-256) — standard. Best of both. "
            "  Adam — adaptive lr per param + momentum. Default for deep learning. "
            "WHY IT MATTERS: neural nets, logistic regression, SVMs, gradient boosting — ALL use GD. "
            "LinearRegression + RandomForest are exceptions (closed-form / greedy). "
            "Backpropagation (neural nets) = chain rule of calculus + GD. "
            "If you understand GD, you understand how most models LEARN."
        ),
        "try_changes": [
            ("Change learning_rate from 0.5 to 0.01", "much slower convergence — needs 200+ steps"),
            ("Change learning_rate from 1.1 to 2.0", "diverges faster — bounces to infinity"),
            ("Change the function from x² to x⁴ (gradient = 4x³)", "steeper — needs smaller lr"),
            ("Add momentum: v = 0.9*v + 0.1*gradient; x -= lr*v", "smoother convergence — Adam-like"),
        ],
    },
    {
        "slug": "ml-maths-probability",
        "category": "ML Advanced",
        "title": "Probability for ML — Bayes, distributions, maximum likelihood",
        "language": "python",
        "summary": "ML is applied probability. Understand Bayes' theorem, common distributions, and maximum likelihood estimation.",
        "starter_code": "import numpy as np\nfrom scipy import stats\nimport matplotlib.pyplot as plt\n\n# ════════════════════════════════════════════════════════════════════\n#  1. BAYES' THEOREM — the foundation of probabilistic ML\n# ════════════════════════════════════════════════════════════════════\nprint('='*60)\nprint('1. BAYES\\' THEOREM')\nprint('='*60)\nprint('P(A|B) = P(B|A) * P(A) / P(B)')\nprint()\nprint('Example: spam detection')\nprint('  A = email is spam')\nprint('  B = email contains \"FREE\"')\nprint('  P(A) = 0.3            (30% of emails are spam)')\nprint('  P(B|A) = 0.8          (80% of spam contains \"FREE\")')\nprint('  P(B|¬A) = 0.1         (10% of non-spam contains \"FREE\")')\nprint('  P(B) = P(B|A)*P(A) + P(B|¬A)*P(¬A) = 0.8*0.3 + 0.1*0.7 = 0.31')\nprint()\n\np_a = 0.3\np_b_given_a = 0.8\np_b_given_not_a = 0.1\np_b = p_b_given_a * p_a + p_b_given_not_a * (1 - p_a)\np_a_given_b = p_b_given_a * p_a / p_b\nprint(f'  P(spam | \"FREE\") = {p_a_given_b:.3f}')\nprint(f'  Even though 80% of spam has \"FREE\", only {p_a_given_b*100:.1f}% of \"FREE\" emails are spam.')\nprint(f'  This is the BASE RATE FALLACY — people ignore P(A).')\nprint(f'  Naive Bayes classifier uses this for EVERY feature.')\n\n# ════════════════════════════════════════════════════════════════════\n#  2. COMMON DISTRIBUTIONS — what shape is your data?\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('2. COMMON DISTRIBUTIONS')\nprint('='*60)\nfig, axes = plt.subplots(2, 3, figsize=(15, 8))\n\n# Normal (Gaussian) — height, age, errors\nx = np.linspace(-5, 5, 100)\naxes[0,0].plot(x, stats.norm.pdf(x, 0, 1), color='#a0c000', linewidth=2)\naxes[0,0].set_title('Normal (Gaussian)\\nheight, age, errors')\naxes[0,0].axvline(0, color='gray', linestyle='--', alpha=0.5)\n\n# Lognormal — income, prices, word frequencies\nx = np.linspace(0, 5, 100)\naxes[0,1].plot(x, stats.lognorm.pdf(x, 0.5), color='#58a6ff', linewidth=2)\naxes[0,1].set_title('Lognormal\\nincome, prices, word freq')\n\n# Uniform — random numbers, dice\nx = np.linspace(0, 1, 100)\naxes[0,2].plot(x, stats.uniform.pdf(x), color='#bc8cff', linewidth=2)\naxes[0,2].set_title('Uniform\\ndice, random sampling')\n\n# Bernoulli — coin flip, binary outcome\naxes[1,0].bar([0, 1], [0.3, 0.7], color='#f85149')\naxes[1,0].set_title('Bernoulli\\ncoin flip, click/no-click')\naxes[1,0].set_xticks([0, 1])\n\n# Binomial — n coin flips\nx = np.arange(0, 11)\naxes[1,1].bar(x, stats.binom.pmf(x, 10, 0.5), color='#ffa657')\naxes[1,1].set_title('Binomial\\n# heads in 10 flips')\n\n# Poisson — events per time period\nx = np.arange(0, 15)\naxes[1,2].bar(x, stats.poisson.pmf(x, 3), color='#3fb950')\naxes[1,2].set_title('Poisson\\n# emails per hour')\n\nplt.tight_layout()\nplt.savefig('distributions.png', dpi=100, bbox_inches='tight')\nplt.show()\nprint('Normal: symmetric, bell-shaped. Height, age, measurement errors.')\nprint('Lognormal: right-skewed. Income, prices, city populations.')\nprint('Uniform: flat. Random sampling, dice rolls.')\nprint('Bernoulli: 0 or 1. Click/no-click, spam/not-spam.')\nprint('Binomial: count of successes. # heads in N flips.')\nprint('Poisson: count of events. # emails per hour, # accidents per month.')\n\n# ════════════════════════════════════════════════════════════════════\n#  3. MAXIMUM LIKELIHOOD ESTIMATION (MLE)\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('3. MAXIMUM LIKELIHOOD ESTIMATION (MLE)')\nprint('='*60)\nprint('Idea: find the parameters that make the observed data MOST LIKELY.')\nprint()\nprint('Example: coin flipped 10 times, 7 heads. Is it fair?')\nprint('  Likelihood: P(data | p) = C(10,7) * p^7 * (1-p)^3')\nprint('  Maximize over p: take derivative, set to 0.')\nprint('  Result: p = 7/10 = 0.7 (the sample proportion)')\n\n# Plot the likelihood function\np_values = np.linspace(0, 1, 100)\nlikelihood = p_values**7 * (1 - p_values)**3\nfig, ax = plt.subplots(figsize=(8, 4))\nax.plot(p_values, likelihood, color='#a0c000', linewidth=2)\nax.axvline(0.7, color='red', linestyle='--', label=f'MLE: p=0.7')\nax.set_xlabel('p (probability of heads)')\nax.set_ylabel('Likelihood')\nax.set_title('Likelihood function — MLE finds the peak')\nax.legend()\nplt.tight_layout()\nplt.savefig('mle.png', dpi=100, bbox_inches='tight')\nplt.show()\nprint(f'\\nMLE: p = {0.7} — the peak of the likelihood function.')\nprint()\nprint('LinearRegression = MLE of Gaussian noise.')\nprint('LogisticRegression = MLE of Bernoulli outcome.')\nprint('Neural Network (cross-entropy loss) = MLE of categorical outcome.')\nprint('MLE is the bridge between probability theory and ML training.')",
        "html_template": "",
        "explanation": (
            "ML = applied probability. 3 concepts to know: "
            "BAYES' THEOREM: P(A|B) = P(B|A)*P(A)/P(B). Update beliefs with evidence. "
            "  Used in: Naive Bayes, Bayesian inference, A/B testing. "
            "  Base rate fallacy: people ignore P(A). 80% of spam has 'FREE' ≠ most 'FREE' emails are spam. "
            "DISTRIBUTIONS: know the shape of your data. "
            "  Normal — symmetric (height, age, errors). "
            "  Lognormal — right-skewed (income, prices). Log-transform to make normal. "
            "  Uniform — flat (random sampling). "
            "  Bernoulli — 0/1 (click/no-click). "
            "  Binomial — count of successes (# heads in N flips). "
            "  Poisson — count of events per period (# emails/hour). "
            "MLE (Maximum Likelihood Estimation): find params that make data MOST LIKELY. "
            "  LinearRegression = MLE of Gaussian noise. "
            "  LogisticRegression = MLE of Bernoulli. "
            "  Cross-entropy loss = MLE of categorical. "
            "  MLE is the bridge: probability theory → ML training. "
            "Understand these 3 = understand why ML models use the loss functions they do."
        ),
        "try_changes": [
            ("Change P(A) from 0.3 to 0.5", "P(spam|FREE) jumps — base rate matters"),
            ("Change the Bernoulli p from 0.7 to 0.3", "bar chart flips — more 0s than 1s"),
            ("Change Poisson lambda from 3 to 10", "distribution shifts right — more events per period"),
            ("Change the MLE example: 70 heads in 100 flips", "MLE = 0.7 still, but confidence higher"),
        ],
    },

    # ═══════════════ SECTION: MODELS ═══════════════
    {
        "slug": "ml-model-selection-thinking",
        "category": "ML Advanced",
        "title": "Model selection — which algorithm for which problem?",
        "language": "python",
        "summary": "Not 'try RandomForest'. A decision framework: data size, feature type, interpretability need, linearity assumption. Pick the RIGHT model.",
        "starter_code": "import numpy as np\nimport pandas as pd\nfrom sklearn.linear_model import LinearRegression, LogisticRegression, Ridge\nfrom sklearn.ensemble import RandomForestRegressor, RandomForestClassifier, GradientBoostingRegressor\nfrom sklearn.svm import SVR, SVC\nfrom sklearn.neighbors import KNeighborsRegressor\nfrom sklearn.tree import DecisionTreeRegressor\nfrom sklearn.datasets import make_regression, make_classification\nfrom sklearn.model_selection import cross_val_score\nimport time\n\n# ════════════════════════════════════════════════════════════════════\n#  THE DECISION FRAMEWORK — 5 questions to pick a model\n# ════════════════════════════════════════════════════════════════════\nprint('='*60)\nprint('MODEL SELECTION — 5 questions')\nprint('='*60)\nprint('Q1: REGRESSION or CLASSIFICATION?')\nprint('  Regression: target is continuous (price, age, temperature)')\nprint('  Classification: target is categorical (spam/not, species A/B/C)')\nprint()\nprint('Q2: How MUCH data?')\nprint('  < 100 rows: LinearRegression/LogisticRegression (low variance)')\nprint('  100-10k: anything works')\nprint('  > 100k: avoid KNN/SVM (slow), use trees or linear')\nprint()\nprint('Q3: LINEAR or NON-LINEAR relationship?')\nprint('  Linear (scatter plot shows a line): LinearRegression, LogisticRegression')\nprint('  Non-linear (curve, clusters): RandomForest, GradientBoosting, SVM(rbf)')\nprint()\nprint('Q4: Need INTERPRETABILITY?')\nprint('  Yes (medical, legal, finance): LinearRegression, DecisionTree, LogisticRegression')\nprint('  No (competitions, raw accuracy): RandomForest, XGBoost, Neural Net')\nprint()\nprint('Q5: How many FEATURES?')\nprint('  < 50: anything works')\nprint('  50-1000: LinearRegression, RandomForest, XGBoost')\nprint('  > 1000 (text, images): LinearModel (sparse), Neural Net, or reduce dimensions first')\n\n# ════════════════════════════════════════════════════════════════════\n#  BENCHMARK: compare 6 models on the same dataset\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('BENCHMARK: 6 regression models on the same data')\nprint('='*60)\n\nX, y = make_regression(n_samples=500, n_features=10, noise=15, random_state=42)\n\nmodels = {\n    'LinearRegression':      LinearRegression(),\n    'Ridge':                 Ridge(alpha=1.0),\n    'DecisionTree':          DecisionTreeRegressor(max_depth=5, random_state=42),\n    'RandomForest':          RandomForestRegressor(n_estimators=50, random_state=42),\n    'GradientBoosting':      GradientBoostingRegressor(n_estimators=50, random_state=42),\n    'KNN':                   KNeighborsRegressor(n_neighbors=5),\n    'SVR':                   SVR(kernel='rbf'),\n}\n\nresults = []\nfor name, model in models.items():\n    t0 = time.perf_counter()\n    scores = cross_val_score(model, X, y, cv=5, scoring='r2')\n    elapsed = time.perf_counter() - t0\n    results.append({\n        'model': name,\n        'R2_mean': scores.mean(),\n        'R2_std': scores.std(),\n        'time_sec': elapsed,\n    })\n\ndf = pd.DataFrame(results).set_index('model')\nprint(df.round(3).to_string())\n\n# ════════════════════════════════════════════════════════════════════\n#  ANALYSIS — when to pick which\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('WHEN TO PICK WHICH')\nprint('='*60)\nbest_r2 = df['R2_mean'].idxmax()\nfastest = df['time_sec'].idxmin()\nprint(f'Best R²:  {best_r2} ({df.loc[best_r2, \"R2_mean\"]:.4f})')\nprint(f'Fastest:  {fastest} ({df.loc[fastest, \"time_sec\"]:.3f}s)')\nprint()\nprint('LinearRegression: FAST, interpretable, baseline. Use FIRST.')\nprint('  Good when: linear relationship, few features, need interpretability.')\nprint('  Bad when: non-linear, high dimensions, multicollinearity (use Ridge).')\nprint()\nprint('RandomForest: accurate, handles non-linearity, no scaling needed.')\nprint('  Good when: non-linear, mixed feature types, medium data.')\nprint('  Bad when: > 1M rows (slow), need extrapolation (trees can\\'t).')\nprint()\nprint('GradientBoosting (XGBoost/LightGBM): HIGHEST accuracy, competition winner.')\nprint('  Good when: max accuracy, tabular data, have time to tune.')\nprint('  Bad when: small data (overfits), need interpretability.')\nprint()\nprint('KNN: simple, no training. Just store data + vote.')\nprint('  Good when: very small data, few features, non-linear.')\nprint('  Bad when: many features (curse of dimensionality), large data (slow predict).')\nprint()\nprint('SVM: powerful with kernels, good for small data.')\nprint('  Good when: small data, high dimensions (text), clear margin.')\nprint('  Bad when: large data (O(n²) or worse), need probabilities.')\nprint()\nprint('NEURAL NETS: not in this benchmark. Use for: images, text, audio.')\nprint('  Bad for: tabular data (XGBoost usually wins), small data (overfits).')\nprint('  Rule: try XGBoost first. If it doesn\\'t win, then try deep learning.')",
        "html_template": "",
        "explanation": (
            "Model selection = matching algorithm to problem. 5 questions: "
            "Q1: Regression (continuous target) vs Classification (categorical target). "
            "Q2: Data size. <100 = linear models. 100-10k = anything. >100k = avoid KNN/SVM. "
            "Q3: Linear vs non-linear. Plot scatter. Linear line → LinearRegression. Curve → trees/SVM. "
            "Q4: Interpretability. Medical/legal/finance → linear/tree. Competition → XGBoost/neural net. "
            "Q5: Feature count. <50 = anything. 50-1000 = linear/trees. >1000 = linear/neural/reduce dims. "
            "RULE OF THUMB: "
            "  Start with LinearRegression/LogisticRegression (baseline). "
            "  Try RandomForest (handles non-linearity, no scaling). "
            "  If accuracy matters most: XGBoost/LightGBM. "
            "  If data is images/text/audio: neural nets. "
            "  If data is small + high-dim: SVM. "
            "  If you need interpretability: DecisionTree or linear. "
            "NEVER start with neural nets on tabular data — XGBoost almost always wins."
        ),
        "try_changes": [
            ("Change n_samples from 500 to 50", "linear models will win — small data favors low-variance models"),
            ("Change n_features from 10 to 100", "KNN will do worse — curse of dimensionality"),
            ("Change noise from 15 to 50", "all models do worse — harder problem"),
            ("Add make_classification + compare LogisticRegression vs RandomForestClassifier", "classification version of the same benchmark"),
        ],
    },
    {
        "slug": "ml-overfitting-understanding",
        "category": "ML Advanced",
        "title": "Overfitting — the #1 reason ML models fail in production",
        "language": "python",
        "summary": "Understand the bias-variance tradeoff, why train > test means overfitting, and 5 techniques to fix it. This is what separates seniors from freshers.",
        "starter_code": "import numpy as np\nimport matplotlib.pyplot as plt\nfrom sklearn.preprocessing import PolynomialFeatures\nfrom sklearn.linear_model import LinearRegression\nfrom sklearn.pipeline import Pipeline\nfrom sklearn.model_selection import train_test_split\n\n# ── Generate data with a TRUE relationship: y = sin(x) + noise ──\nnp.random.seed(42)\nn = 30\nx = np.sort(np.random.uniform(0, 5, n))\ny_true = np.sin(x)\ny = y_true + np.random.normal(0, 0.2, n)\n\n# ── Train models with INCREASING complexity (polynomial degree) ──\ndegrees = [1, 3, 5, 15]\nfig, axes = plt.subplots(1, 4, figsize=(20, 5))\n\nfor ax, degree in zip(axes, degrees):\n    # Pipeline: polynomial features + linear regression\n    model = Pipeline([\n        ('poly', PolynomialFeatures(degree=degree)),\n        ('linear', LinearRegression())\n    ])\n    model.fit(x.reshape(-1, 1), y)\n\n    # Train + test scores\n    x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=0.3, random_state=42)\n    model.fit(x_train.reshape(-1, 1), y_train)\n    train_score = model.score(x_train.reshape(-1, 1), y_train)\n    test_score = model.score(x_test.reshape(-1, 1), y_test)\n\n    # Plot\n    x_plot = np.linspace(0, 5, 100)\n    y_plot = model.predict(x_plot.reshape(-1, 1))\n    ax.scatter(x_train, y_train, color='#a0c000', label='train', s=30)\n    ax.scatter(x_test, y_test, color='#f85149', label='test', s=30, marker='x')\n    ax.plot(x_plot, y_plot, color='#58a6ff', linewidth=2, label='model')\n    ax.plot(x_plot, np.sin(x_plot), color='#888', linestyle='--', label='true (sin)')\n    ax.set_title(f'Degree {degree}\\ntrain R²={train_score:.3f}, test R²={test_score:.3f}')\n    ax.set_ylim(-2, 2)\n    ax.legend(fontsize=8)\n\nplt.tight_layout()\nplt.savefig('overfitting.png', dpi=100, bbox_inches='tight')\nplt.show()\n\n# ════════════════════════════════════════════════════════════════════\n#  WHAT'S HAPPENING — bias vs variance\n# ════════════════════════════════════════════════════════════════════\nprint('='*60)\nprint('BIAS-VARIANCE TRADEOFF')\nprint('='*60)\nprint('Degree 1 (UNDERFITTING): high bias, low variance')\nprint('  train R² low, test R² low. Model is too simple.')\nprint('  The model can\\'t capture the sin curve — it\\'s a straight line.')\nprint()\nprint('Degree 3 (GOOD FIT): balanced bias + variance')\nprint('  train R² high, test R² high. Model captures the pattern.')\nprint()\nprint('Degree 5 (SLIGHT OVERFIT): low bias, higher variance')\nprint('  train R² very high, test R² slightly lower. Starting to memorize.')\nprint()\nprint('Degree 15 (OVERFITTING): very low bias, very high variance')\nprint('  train R² = 1.0 (perfect), test R² NEGATIVE (worse than mean)!')\nprint('  Model memorized the training points + noise. Fails on new data.')\n\n# ════════════════════════════════════════════════════════════════════\n#  5 TECHNIQUES TO FIX OVERFITTING\n# ════════════════════════════════════════════════════════════════════\nprint('\\n' + '='*60)\nprint('5 TECHNIQUES TO FIX OVERFITTING')\nprint('='*60)\nprint('1. MORE DATA: the best fix. More data = model can\\'t memorize all of it.')\nprint('2. SIMPLER MODEL: reduce polynomial degree, tree depth, neural net layers.')\nprint('3. REGULARIZATION: L1 (Lasso) / L2 (Ridge) — penalize large coefficients.')\nprint('4. CROSS-VALIDATION: use 5-fold CV to detect overfitting early.')\nprint('5. EARLY STOPPING: stop training when validation score starts dropping.')\nprint('   (Used in gradient boosting + neural nets.)')\nprint()\nprint('ALWAYS look at BOTH train + test scores:')\nprint('  train >> test = OVERFITTING (reduce complexity)')\nprint('  train ≈ test = good fit (or both bad = underfitting)')\nprint('  train low = UNDERFITTING (increase complexity)')",
        "html_template": "",
        "explanation": (
            "Overfitting = model memorizes training data instead of learning patterns. "
            "Symptom: train R² = 0.99, test R² = 0.50. The gap = overfitting. "
            "BIAS-VARIANCE TRADEOFF: "
            "  High bias (underfitting): model too simple. train + test both low. "
            "  High variance (overfitting): model too complex. train high, test low. "
            "  Sweet spot: train ≈ test, both high. "
            "WHY IT MATTERS: production = new data = the test set scenario. "
            "  A model that's 99% on train but 50% on test is WORTHLESS in production. "
            "5 FIXES: "
            "  (1) More data — best fix. Can't memorize 1M rows. "
            "  (2) Simpler model — reduce degree/depth/layers. "
            "  (3) Regularization — L1 (Lasso) zeros out useless features. L2 (Ridge) shrinks coefficients. "
            "  (4) Cross-validation — 5-fold CV shows if the model generalizes. "
            "  (5) Early stopping — stop when validation score drops. "
            "ALWAYS report train + test scores. If someone only shows train, assume they're hiding overfitting."
        ),
        "try_changes": [
            ("Change degree 15 to 25", "even more extreme overfitting — test R² very negative"),
            ("Increase n from 30 to 300", "more data → less overfitting, even at degree 15"),
            ("Change noise from 0.2 to 1.0", "harder problem — all models do worse"),
            ("Add Ridge regression to the pipeline: from sklearn.linear_model import Ridge", "regularization reduces overfitting"),
        ],
    },

    # ═══════════════ SECTION: REAL-WORLD WORKFLOW ═══════════════
    {
        "slug": "ml-full-workflow",
        "category": "ML Advanced",
        "title": "Full ML workflow — the senior data scientist's process",
        "language": "python",
        "summary": "Not 'load + fit + predict'. The REAL workflow: 10 steps from raw data to production-ready model. This is what senior DS actually do.",
        "starter_code": "import pandas as pd\nimport numpy as np\nfrom sklearn.model_selection import train_test_split, cross_validate, KFold\nfrom sklearn.compose import ColumnTransformer\nfrom sklearn.pipeline import Pipeline\nfrom sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder\nfrom sklearn.impute import SimpleImputer\nfrom sklearn.ensemble import RandomForestRegressor\nfrom sklearn.linear_model import LinearRegression, Ridge\nfrom sklearn.metrics import mean_absolute_error, r2_score\nimport time\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 1: LOAD + UNDERSTAND THE DATA\n# ════════════════════════════════════════════════════════════════════\nprint('STEP 1: LOAD + UNDERSTAND')\nprint('-' * 50)\n# Synthetic dataset (in real life: pd.read_csv('data.csv'))\nnp.random.seed(42)\nn = 1000\ndf = pd.DataFrame({\n    'age': np.random.normal(40, 12, n).clip(18, 80),\n    'income': np.random.lognormal(10.5, 0.6, n),\n    'years_experience': np.random.randint(0, 40, n),\n    'education': np.random.choice(['High School', 'Bachelor', 'Master', 'PhD'], n),\n    'city': np.random.choice(['NYC', 'LA', 'SF', 'Chicago', 'Boston'], n),\n})\ndf['salary'] = (\n    30000 + df['years_experience'] * 2500 +\n    df['education'].map({'High School': 0, 'Bachelor': 4000, 'Master': 8000, 'PhD': 12000}) +\n    np.random.normal(0, 8000, n) +\n    df['city'].map({'NYC': 15000, 'SF': 20000, 'LA': 10000, 'Chicago': 5000, 'Boston': 8000})\n)\n# Inject real-world messiness\ndf.loc[df.sample(50, random_state=42).index, 'age'] = np.nan\nprint(f'Shape: {df.shape}')\nprint(f'Nulls: {df.isnull().sum().sum()}')\nprint(f'Target: salary (continuous → regression)')\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 2: SEPARATE X (features) AND y (target) — BEFORE any processing\n# ════════════════════════════════════════════════════════════════════\nprint('\\nSTEP 2: X/y SPLIT')\nprint('-' * 50)\nX = df.drop(columns=['salary'])\ny = df['salary']\nprint(f'X shape: {X.shape} (features)')\nprint(f'y shape: {y.shape} (target)')\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 3: TRAIN/TEST SPLIT — BEFORE preprocessing (prevents leakage)\n# ════════════════════════════════════════════════════════════════════\nprint('\\nSTEP 3: TRAIN/TEST SPLIT (BEFORE preprocessing)')\nprint('-' * 50)\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)\nprint(f'Train: {len(X_train)} rows')\nprint(f'Test:  {len(X_test)} rows')\nprint('WHY before preprocessing? If you fit the scaler on ALL data,')\nprint('test data leaks into the scaler → optimistic scores.')\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 4: IDENTIFY COLUMN TYPES\n# ════════════════════════════════════════════════════════════════════\nprint('\\nSTEP 4: COLUMN TYPES')\nprint('-' * 50)\nnumerical_features = ['age', 'income', 'years_experience']\ncategorical_nominal = ['city']  # no natural order\ncategorical_ordinal = ['education']  # has order: HS < Bachelor < Master < PhD\nprint(f'Numerical:   {numerical_features}')\nprint(f'Nominal:     {categorical_nominal} (OneHot)')\nprint(f'Ordinal:     {categorical_ordinal} (OrdinalEncoder with explicit order)')\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 5: BUILD PREPROCESSING PIPELINES\n# ════════════════════════════════════════════════════════════════════\nprint('\\nSTEP 5: PREPROCESSING PIPELINES')\nprint('-' * 50)\nnumeric_pipeline = Pipeline([\n    ('imputer', SimpleImputer(strategy='median')),\n    ('scaler', StandardScaler())\n])\nnominal_pipeline = Pipeline([\n    ('imputer', SimpleImputer(strategy='most_frequent')),\n    ('encoder', OneHotEncoder(drop='first', handle_unknown='ignore'))\n])\nordinal_pipeline = Pipeline([\n    ('imputer', SimpleImputer(strategy='most_frequent')),\n    ('encoder', OrdinalEncoder(categories=[['High School', 'Bachelor', 'Master', 'PhD']]))\n])\npreprocessor = ColumnTransformer([\n    ('num', numeric_pipeline, numerical_features),\n    ('nom', nominal_pipeline, categorical_nominal),\n    ('ord', ordinal_pipeline, categorical_ordinal),\n])\nprint('Built 3 pipelines: numeric (impute+scale), nominal (impute+OneHot), ordinal (impute+OrdinalEncoder)')\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 6: CREATE FULL PIPELINE (preprocessing + model)\n# ════════════════════════════════════════════════════════════════════\nprint('\\nSTEP 6: FULL PIPELINE')\nprint('-' * 50)\nmodel = Pipeline([\n    ('preprocessing', preprocessor),\n    ('regressor', RandomForestRegressor(n_estimators=50, random_state=42))\n])\nprint('Pipeline: preprocessing → RandomForestRegressor')\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 7: TRAIN + EVALUATE\n# ════════════════════════════════════════════════════════════════════\nprint('\\nSTEP 7: TRAIN + EVALUATE')\nprint('-' * 50)\nt0 = time.perf_counter()\nmodel.fit(X_train, y_train)\ntrain_time = time.perf_counter() - t0\n\ny_train_pred = model.predict(X_train)\ny_test_pred = model.predict(X_test)\n\nprint(f'Training time: {train_time:.2f}s')\nprint(f'Train R²: {r2_score(y_train, y_train_pred):.4f}')\nprint(f'Test  R²: {r2_score(y_test, y_test_pred):.4f}')\nprint(f'Train MAE: {mean_absolute_error(y_train, y_train_pred):.0f}')\nprint(f'Test  MAE: {mean_absolute_error(y_test, y_test_pred):.0f}')\nprint(f'Gap (overfitting?): {r2_score(y_train, y_train_pred) - r2_score(y_test, y_test_pred):.4f}')\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 8: CROSS-VALIDATION (more honest than single split)\n# ════════════════════════════════════════════════════════════════════\nprint('\\nSTEP 8: CROSS-VALIDATION')\nprint('-' * 50)\ncv = KFold(n_splits=5, shuffle=True, random_state=42)\ncv_results = cross_validate(model, X, y, cv=cv, scoring=['r2', 'neg_mean_absolute_error'])\nprint(f'CV R²:   {cv_results[\"test_r2\"].mean():.4f} ± {cv_results[\"test_r2\"].std():.4f}')\nprint(f'CV MAE:  {-cv_results[\"test_neg_mean_absolute_error\"].mean():.0f}')\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 9: COMPARE MULTIPLE MODELS\n# ════════════════════════════════════════════════════════════════════\nprint('\\nSTEP 9: COMPARE MODELS')\nprint('-' * 50)\nmodels_to_try = {\n    'LinearRegression': Pipeline([('prep', preprocessor), ('model', LinearRegression())]),\n    'Ridge': Pipeline([('prep', preprocessor), ('model', Ridge(alpha=1.0))]),\n    'RandomForest': model,  # already built\n}\nfor name, m in models_to_try.items():\n    scores = cross_validate(m, X, y, cv=cv, scoring='r2')['test_r2']\n    print(f'  {name:20s}  R² = {scores.mean():.4f} ± {scores.std():.4f}')\n\n# ════════════════════════════════════════════════════════════════════\n#  STEP 10: SAVE THE WINNER + DEPLOY\n# ════════════════════════════════════════════════════════════════════\nprint('\\nSTEP 10: SAVE + DEPLOY')\nprint('-' * 50)\nimport joblib\njoblib.dump(model, 'best_model.pkl')\nprint('Saved -> best_model.pkl')\nprint('The pipeline INCLUDES preprocessing — no need to remember the scaler.')\nprint('In production: model = joblib.load(\"best_model.pkl\"); model.predict(new_data)')\nprint('\\nFULL WORKFLOW COMPLETE. This is what senior data scientists do.')",
        "html_template": "",
        "explanation": (
            "10 steps = the real ML workflow. NOT 'load + fit + predict'. "
            "STEP 1: UNDERSTAND — shape, nulls, types, distributions, leaks. "
            "STEP 2: X/y SPLIT — separate features from target BEFORE processing. "
            "STEP 3: TRAIN/TEST SPLIT — BEFORE preprocessing to prevent leakage. "
            "  If you scale on all data, test data leaks into the scaler → fake high scores. "
            "STEP 4: COLUMN TYPES — numerical, nominal (no order), ordinal (has order). "
            "STEP 5: PIPELINES — one per type. Impute + scale for numeric, impute + encode for categorical. "
            "STEP 6: FULL PIPELINE — chain preprocessing + model. One fit(), one predict(). "
            "STEP 7: TRAIN + EVALUATE — report TRAIN + TEST scores. Gap = overfitting. "
            "STEP 8: CROSS-VALIDATION — 5-fold CV. More honest than single split. "
            "STEP 9: COMPARE MODELS — never trust one model. Try 3+, pick the winner. "
            "STEP 10: SAVE THE PIPELINE — preprocessing is BAKED IN. No need to remember the scaler. "
            "WHY THIS MATTERS: skip any step = model fails in production. "
            "  Skip step 3 = data leakage = 99% train, 50% production. "
            "  Skip step 5 = manual preprocessing = forget a step = crash. "
            "  Skip step 8 = lucky split = model worse than you think. "
            "  Skip step 9 = stuck with a bad model = miss easy accuracy. "
            "This is the difference between 'I trained a model' (fresher) and 'I built a production ML system' (senior)."
        ),
        "try_changes": [
            ("Change the model from RandomForestRegressor to GradientBoostingRegressor", "often higher accuracy on tabular data"),
            ("Add a leak column: df['salary_per_year'] = df['salary'] / df['years_experience'].clip(1)", "Step 1 should detect it (high correlation with target)"),
            ("Change the imputation strategy from 'median' to 'mean'", "income is skewed — median is better, mean is pulled by outliers"),
            ("Add Step 9b: hyperparameter tuning with GridSearchCV", "find the best n_estimators for RandomForest"),
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
#  All labs combined
# ═══════════════════════════════════════════════════════════════════════════

ALL_LABS = _CSS_LABS + _HTML_LABS + _PYTHON_LABS + _FASTAPI_LABS + _BENCH_LABS + _ML_ADVANCED_LABS

# Index by slug for O(1) lookup
_LAB_BY_SLUG = {lab["slug"]: lab for lab in ALL_LABS}

# Group by category for the overview page
_LABS_BY_CATEGORY = {
    "Python":           _PYTHON_LABS,
    "HTML":             _HTML_LABS,
    "CSS":              _CSS_LABS,
    "FastAPI":          _FASTAPI_LABS,
    "Benchmark Engine": _BENCH_LABS,
    "ML Advanced":      _ML_ADVANCED_LABS,
}

# Display order for categories
_CATEGORY_ORDER = ["Python", "HTML", "CSS", "FastAPI", "Benchmark Engine", "ML Advanced"]

# Per-category metadata for the overview page
_CATEGORY_META = {
    "Python":           {"icon": "&#128013;", "color": "#3fb950", "blurb": "Variables, loops, functions, lists, dicts, classes — the language the whole backend is written in."},
    "HTML":             {"icon": "&#127760;", "color": "#58a6ff", "blurb": "Tags, forms, semantic structure. The skeleton of every web page."},
    "CSS":              {"icon": "&#127912;", "color": "#bc8cff", "blurb": "Classic CSS (no Tailwind, no framework). Colors, borders, box-shadow, flexbox, grid, transitions."},
    "FastAPI":          {"icon": "&#9889;",   "color": "#a0c000", "blurb": "Routes, params, Pydantic, templates, dependencies, websockets — the web framework."},
    "Benchmark Engine": {"icon": "&#9889;",   "color": "#ffa657", "blurb": "Build a benchmarking engine for ANY .pkl model — load, predict, time, metrics, compare. Like OpenBenchML."},
    "ML Advanced":      {"icon": "&#129504;", "color": "#f85149", "blurb": "The THINKING process — preprocessing, EDA, maths, model selection, overfitting. For data scientists who want to handle ANY dataset."},
}


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/learn/labs", response_class=HTMLResponse)
async def learn_labs_overview(request: Request):
    """Render the labs overview — all labs grouped by category."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    return templates.TemplateResponse("learn_lab.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "view": "overview",
        "labs_by_category": _LABS_BY_CATEGORY,
        "category_order": _CATEGORY_ORDER,
        "category_meta": _CATEGORY_META,
        "total_labs": len(ALL_LABS),
    })


@router.get("/learn/labs/{slug}", response_class=HTMLResponse)
async def learn_lab_page(request: Request, slug: str):
    """Render a single lab page — code editor + live preview."""
    db = SessionLocal()
    try:
        user = await get_current_user_from_cookie(request, db)
    finally:
        db.close()

    lab = _LAB_BY_SLUG.get(slug)
    if lab is None:
        raise HTTPException(status_code=404, detail=f"Lab '{slug}' not found")

    # Find prev/next within the same category
    cat_labs = _LABS_BY_CATEGORY.get(lab["category"], [])
    idx = next((i for i, l in enumerate(cat_labs) if l["slug"] == slug), -1)
    prev_lab = cat_labs[idx - 1] if idx > 0 else None
    next_lab = cat_labs[idx + 1] if idx < len(cat_labs) - 1 else None

    return templates.TemplateResponse("learn_lab.html", {
        "request": request,
        "user": user,
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "view": "lab",
        "lab": lab,
        "prev_lab": prev_lab,
        "next_lab": next_lab,
        "category_meta": _CATEGORY_META,
        "total_labs": len(ALL_LABS),
    })
