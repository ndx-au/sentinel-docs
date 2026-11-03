# Sentinel documentation reading rooms

Three XSLT 3.0 entry stylesheets share `common.xsl` for Markdown rendering:

- Atlas: persistent library sidebar, article, and separate page outline.
- Folio: editorial title spread and numbered chapters grouped from level-two headings.
- Console: operations sidebar and expandable modules grouped from level-two headings.

The kit selects `cms_theme: showcase`; the manifest maps the existing `docs` template to Atlas. The HTTP view selector chooses `atlas`, `folio`, or `console` through the `view` query parameter and preserves the document URL. Local storage remembers the chosen reading room. Shared CSS lives in `pb/showcase.css`; the selector behavior is in `pb/showcase.js`.

References consulted: https://docs.stripe.com/ (reference navigation), https://docs.deno.com/ (developer documentation hierarchy), and https://motherfuckingwebsite.com/ (radical typographic simplicity). These are original layouts, not copies of those sites. An XSL-specific agent skill was searched for; no suitable reviewed candidate was identified or installed.
