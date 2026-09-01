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
#  All labs combined
# ═══════════════════════════════════════════════════════════════════════════

ALL_LABS = _CSS_LABS + _HTML_LABS + _PYTHON_LABS + _FASTAPI_LABS

# Index by slug for O(1) lookup
_LAB_BY_SLUG = {lab["slug"]: lab for lab in ALL_LABS}

# Group by category for the overview page
_LABS_BY_CATEGORY = {
    "Python":  _PYTHON_LABS,
    "HTML":    _HTML_LABS,
    "CSS":     _CSS_LABS,
    "FastAPI": _FASTAPI_LABS,
}

# Display order for categories
_CATEGORY_ORDER = ["Python", "HTML", "CSS", "FastAPI"]

# Per-category metadata for the overview page
_CATEGORY_META = {
    "Python":  {"icon": "&#128013;", "color": "#3fb950", "blurb": "Variables, loops, functions, lists, dicts, classes — the language the whole backend is written in."},
    "HTML":    {"icon": "&#127760;", "color": "#58a6ff", "blurb": "Tags, forms, semantic structure. The skeleton of every web page."},
    "CSS":     {"icon": "&#127912;", "color": "#bc8cff", "blurb": "Classic CSS (no Tailwind, no framework). Colors, borders, box-shadow, flexbox, grid, transitions."},
    "FastAPI": {"icon": "&#9889;",   "color": "#a0c000", "blurb": "Routes, params, Pydantic, templates, dependencies, websockets — the web framework."},
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
