/**
 * Minimal, dependency-free Markdown -> HTML renderer.
 * Output is always escaped before formatting, so raw user content can never
 * inject markup. Intentionally small: headings, fenced code, lists, quotes,
 * inline code and bold. (Phase 1 preview does not need full CommonMark.)
 */

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function renderInline(text: string): string {
  return text
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
}

export function renderMarkdown(source: string): string {
  const escaped = escapeHtml(source.replace(/\r\n?/g, '\n'))
  const lines = escaped.split('\n')
  const out: string[] = []
  let inCode = false
  let codeLines: string[] = []
  let listTag: 'ul' | 'ol' | null = null

  const closeList = () => {
    if (listTag) {
      out.push(`</${listTag}>`)
      listTag = null
    }
  }

  for (const line of lines) {
    if (line.trim().startsWith('```')) {
      if (inCode) {
        out.push(`<pre class="md-code"><code>${codeLines.join('\n')}</code></pre>`)
        codeLines = []
        inCode = false
      } else {
        closeList()
        inCode = true
      }
      continue
    }

    if (inCode) {
      codeLines.push(line)
      continue
    }

    const heading = /^(#{1,6})\s+(.*)$/.exec(line)
    if (heading) {
      closeList()
      const level = heading[1].length
      out.push(`<h${level}>${renderInline(heading[2])}</h${level}>`)
      continue
    }

    const unordered = /^\s*[-*+]\s+(.*)$/.exec(line)
    if (unordered) {
      if (listTag !== 'ul') {
        closeList()
        out.push('<ul>')
        listTag = 'ul'
      }
      out.push(`<li>${renderInline(unordered[1])}</li>`)
      continue
    }

    const ordered = /^\s*\d+\.\s+(.*)$/.exec(line)
    if (ordered) {
      if (listTag !== 'ol') {
        closeList()
        out.push('<ol>')
        listTag = 'ol'
      }
      out.push(`<li>${renderInline(ordered[1])}</li>`)
      continue
    }

    const quote = /^\s*>\s?(.*)$/.exec(line)
    if (quote) {
      closeList()
      out.push(`<blockquote>${renderInline(quote[1])}</blockquote>`)
      continue
    }

    if (line.trim() === '') {
      closeList()
      continue
    }

    closeList()
    out.push(`<p>${renderInline(line.replace(/\s+$/, ''))}</p>`)
  }

  if (inCode) {
    out.push(`<pre class="md-code"><code>${codeLines.join('\n')}</code></pre>`)
  }
  closeList()
  return out.join('\n')
}
