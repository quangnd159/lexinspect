# LexInspect icon

Approved design: a traditional graphite magnifying glass over a composed text sheet, with a script l, an inline mint word highlight, and a 13% optical enlargement.

- `LexInspect.icon` is the editable Icon Composer master. All artwork is vector, arranged in four physical groups: graphite, ink, optical glass, and reading sheet.
- `LexInspect Exports/` contains the six native 1024 px appearance exports from Icon Composer.
- `build.py` deterministically rebuilds the SVG artboards and icon document with Python 3's standard library. Native lighting and appearance rendering remain in Icon Composer.
- The source script l is an outlined Times script glyph. No font is needed to open or render the master.
- The site's header icons, favicons and touch icon are reduced from the native exports, not screenshots.

Open `LexInspect.icon` in Icon Composer. Use the 26 and 27 effects previews to inspect platform rendering; the light and dark background variants are defined in the document.
