import React from 'react'

export interface HighlightOptions {
  highlightTag?: string
  highlightClassName?: string
  highlightStyle?: React.CSSProperties
  maxLength?: number
  contextLength?: number
}

export const highlightText = (
  text: string,
  keywords: string[],
  options: HighlightOptions = {}
): React.ReactNode => {
  const {
    highlightTag = 'mark',
    highlightClassName = 'search-highlight',
    highlightStyle = { backgroundColor: '#ffc069', padding: '0 2px', borderRadius: '2px' },
    maxLength = 200,
    contextLength = 50,
  } = options

  if (!text || keywords.length === 0) {
    return text
  }

  const lowerText = text.toLowerCase()
  const lowerKeywords = keywords.map((k) => k.toLowerCase())

  const matches: Array<{ start: number; end: number; keyword: string }> = []

  lowerKeywords.forEach((keyword) => {
    let startIndex = 0
    while (true) {
      const index = lowerText.indexOf(keyword, startIndex)
      if (index === -1) break
      matches.push({
        start: index,
        end: index + keyword.length,
        keyword: keyword,
      })
      startIndex = index + 1
    }
  })

  if (matches.length === 0) {
    return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text
  }

  matches.sort((a, b) => a.start - b.start)

  const mergedMatches: Array<{ start: number; end: number }> = []
  let current = matches[0]
  for (let i = 1; i < matches.length; i++) {
    if (matches[i].start <= current.end) {
      current.end = Math.max(current.end, matches[i].end)
    } else {
      mergedMatches.push(current)
      current = matches[i]
    }
  }
  mergedMatches.push(current)

  let displayText = text
  let offset = 0

  if (text.length > maxLength) {
    const firstMatch = mergedMatches[0]
    const contextStart = Math.max(0, firstMatch.start - contextLength)
    const contextEnd = Math.min(text.length, firstMatch.end + contextLength)

    displayText = (contextStart > 0 ? '...' : '') +
      text.substring(contextStart, contextEnd) +
      (contextEnd < text.length ? '...' : '')

    offset = -contextStart + (contextStart > 0 ? 3 : 0)
  }

  const result: React.ReactNode[] = []
  let lastIndex = 0

  mergedMatches.forEach((match, index) => {
    const adjustedStart = match.start + offset
    const adjustedEnd = match.end + offset

    if (adjustedStart > lastIndex) {
      result.push(displayText.substring(lastIndex, adjustedStart))
    }

    const highlightedText = displayText.substring(adjustedStart, adjustedEnd)
    result.push(
      React.createElement(
        highlightTag,
        {
          key: index,
          className: highlightClassName,
          style: highlightStyle,
        },
        highlightedText
      )
    )

    lastIndex = adjustedEnd
  })

  if (lastIndex < displayText.length) {
    result.push(displayText.substring(lastIndex))
  }

  return result.length === 1 && typeof result[0] === 'string' ? result[0] : result
}

export const extractKeywords = (query: string): string[] => {
  if (!query) return []

  const keywords = query
    .split(/\s+/)
    .map((k) => k.trim())
    .filter((k) => k.length > 0)

  return [...new Set(keywords)]
}

export const getSearchContext = (
  text: string,
  keyword: string,
  contextLength: number = 50
): string => {
  if (!text || !keyword) return text

  const lowerText = text.toLowerCase()
  const lowerKeyword = keyword.toLowerCase()
  const index = lowerText.indexOf(lowerKeyword)

  if (index === -1) {
    return text.length > contextLength * 2
      ? `${text.substring(0, contextLength * 2)}...`
      : text
  }

  const start = Math.max(0, index - contextLength)
  const end = Math.min(text.length, index + keyword.length + contextLength)

  const context = text.substring(start, end)

  return (
    (start > 0 ? '...' : '') +
    context +
    (end < text.length ? '...' : '')
  )
}

export const calculateRelevanceScore = (
  text: string,
  keywords: string[]
): number => {
  if (!text || keywords.length === 0) return 0

  const lowerText = text.toLowerCase()
  let score = 0

  keywords.forEach((keyword) => {
    const lowerKeyword = keyword.toLowerCase()
    const count = (lowerText.match(new RegExp(lowerKeyword, 'g')) || []).length
    score += count * keyword.length
  })

  return score / text.length
}
