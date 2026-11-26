<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:param name="layout" select="'atlas'"/>
<xsl:template name="picker"><label class="picker">Reading room <select id="layout-picker" aria-label="Documentation layout"><option value="atlas">Atlas · Reference desk</option><option value="folio">Folio · Field journal</option><option value="console">Console · Operations</option></select></label></xsl:template>
<xsl:template name="nav"><nav aria-label="Documentation"><a href="/index?view={$layout}">Overview</a><a href="/getting-started?view={$layout}">Getting Started</a><a href="/api-reference?view={$layout}">API Reference</a><a href="/lua-api?view={$layout}">Lua API</a><a href="/cli-reference?view={$layout}">CLI Reference</a><a href="/configuration-guide?view={$layout}">Configuration Guide</a><a href="/kit-development?view={$layout}">Kit Development</a><a href="/workflows-and-patterns?view={$layout}">Workflows &amp; Patterns</a><a href="/troubleshooting-faq?view={$layout}">Troubleshooting &amp; FAQ</a><a href="/triple-access-pattern?view={$layout}">Triple Access Pattern</a><a href="/edge-deployment?view={$layout}">Edge Deployment</a><a href="/adversarial-testing?view={$layout}">Adversarial Testing</a><a href="/storage?view={$layout}">Storage</a><a href="/licensing?view={$layout}">Licensing</a><a href="/docker-and-containers?view={$layout}">Docker &amp; Containers</a><a href="/wordpress?view={$layout}">WordPress</a><a href="/harness-http-routes?view={$layout}">Harness HTTP Routes</a><a href="/sentinel-directory?view={$layout}">The .sentinel/ Directory</a><a href="/sentinel-cms?view={$layout}">fcms (file CMS)</a><a href="/mcp-agent-integration?view={$layout}">MCP &amp; Agent Integration</a><a href="/agent-skills?view={$layout}">Agent Skills Library</a><a href="/internals?view={$layout}">Internals</a><a href="/agentic-ai-operator?view={$layout}">Agentic AI Operator</a><a href="/rag-evaluation?view={$layout}">RAG Evaluation</a><a href="/ai-provider-extension?view={$layout}">AI Provider Extension</a><a href="/content-planes?view={$layout}">Content Planes</a><a href="/ndx-trust-soc2?view={$layout}">NDX Trust &amp; SOC 2</a><a href="/agentic-ai-uat?view={$layout}">Agentic AI UAT</a></nav></xsl:template>
<xsl:template name="toc"><nav aria-label="On this page"><p class="eyebrow">On this page</p><xsl:for-each select="/document/content/heading[@level='2']"><a href="#{@id}"><xsl:value-of select="."/></a></xsl:for-each></nav></xsl:template>
<xsl:template name="footer-qr"><div class="footer-qr"><a class="footer-qr-link" href="https://docs.ndx-sentinel.com" aria-label="Open https://docs.ndx-sentinel.com"><img src="/kt/sn/docs/pb/docs-qr.svg" alt="QR code linking to https://docs.ndx-sentinel.com" width="96" height="96" loading="lazy"/><span class="footer-qr-meta"><span class="eyebrow">Sentinel Docs</span><strong>https://docs.ndx-sentinel.com</strong><span class="footer-qr-hint">Scan or open on another device.</span></span></a></div></xsl:template>
<xsl:template name="head"><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title><xsl:value-of select="/document/metadata/field[@name='title']"/> — Sentinel</title><link rel="stylesheet" href="/kt/sn/docs/pb/showcase.css"/><script src="/kt/sn/docs/pb/showcase.js" defer="defer"></script></xsl:template>
<xsl:template match="heading"><xsl:element name="h{@level}"><xsl:attribute name="id" select="@id"/><xsl:apply-templates/></xsl:element></xsl:template>
<xsl:template match="paragraph"><p><xsl:apply-templates/></p></xsl:template>
<xsl:template match="text"><xsl:value-of select="."/><xsl:if test="@hardbreak='true' or @softbreak='true'"><br/></xsl:if></xsl:template>
<xsl:template match="emphasis"><xsl:choose><xsl:when test="@level='2'"><strong><xsl:apply-templates/></strong></xsl:when><xsl:otherwise><em><xsl:apply-templates/></em></xsl:otherwise></xsl:choose></xsl:template>
<xsl:template match="link|autolink"><a href="{@destination}" title="{@title}"><xsl:apply-templates/></a></xsl:template>
<!-- Staging and production share the same public bucket for Markdown /img/ paths. -->
<xsl:variable name="image-base-url" select="'https://sentinel-docs.s3.us-east-005.backblazeb2.com/'"/>
<xsl:template match="image">
  <xsl:variable name="src" select="if (starts-with(@destination, '/img/'))
    then concat($image-base-url, substring-after(@destination, '/img/'))
    else @destination"/>
  <img src="{$src}" alt="{.}" title="{@title}" loading="lazy"/>
</xsl:template>
<xsl:template match="list"><xsl:choose><xsl:when test="@ordered='true'"><ol start="{@start}"><xsl:apply-templates/></ol></xsl:when><xsl:otherwise><ul><xsl:apply-templates/></ul></xsl:otherwise></xsl:choose></xsl:template>
<xsl:template match="listitem"><li><xsl:apply-templates/></li></xsl:template>
<xsl:template match="blockquote"><blockquote><xsl:apply-templates/></blockquote></xsl:template>
<xsl:template match="codespan"><code><xsl:value-of select="."/></code></xsl:template>
<xsl:template match="codeblock|fencedcodeblock"><pre><code class="language-{@language}"><xsl:value-of select="."/></code></pre></xsl:template>
<xsl:template match="table"><div class="table-scroll" tabindex="0" role="region" aria-label="Table"><table class="responsive-table"><xsl:apply-templates select="tableheader"/><tbody><xsl:apply-templates select="tablerow"/></tbody></table></div></xsl:template>
<xsl:template match="tableheader"><thead><tr><xsl:apply-templates/></tr></thead></xsl:template>
<xsl:template match="tablerow"><tr><xsl:apply-templates/></tr></xsl:template>
<xsl:template match="tablecell"><xsl:choose><xsl:when test="parent::tableheader"><th scope="col"><xsl:apply-templates/></th></xsl:when><xsl:otherwise><xsl:variable name="col" select="count(preceding-sibling::tablecell) + 1"/><xsl:variable name="hdr" select="normalize-space(string(ancestor::table[1]/tableheader[1]/tablecell[$col]))"/><td data-label="{$hdr}"><xsl:apply-templates/></td></xsl:otherwise></xsl:choose></xsl:template>
<xsl:template match="strikethrough"><del><xsl:apply-templates/></del></xsl:template>
<xsl:template match="thematicbreak"><hr/></xsl:template>
<xsl:template match="taskcheckbox"><input type="checkbox" disabled="disabled"><xsl:if test="@checked='true'"><xsl:attribute name="checked">checked</xsl:attribute></xsl:if></input></xsl:template>
<xsl:template match="rawhtml|htmlblock"><xsl:value-of select="replace(., '&lt;!-- ndx-ste-mode: description --&gt;', '')" disable-output-escaping="yes"/></xsl:template>
</xsl:stylesheet>
