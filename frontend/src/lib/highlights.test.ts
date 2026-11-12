import { describe, expect, it } from 'vitest'

import { groupHighlights, highlightsToText, textToHighlights } from './highlights'

describe('textToHighlights', () => {
  it('reads one bullet per line, ignoring blank lines', () => {
    expect(textToHighlights('a\n\n  b  \n')).toEqual([
      { text: 'a', group: null },
      { text: 'b', group: null },
    ])
  })

  it('applies a ## line to the bullets that follow it', () => {
    expect(textToHighlights('x\n## Platform\na\nb\n## Quality\nc')).toEqual([
      { text: 'x', group: null },
      { text: 'a', group: 'Platform' },
      { text: 'b', group: 'Platform' },
      { text: 'c', group: 'Quality' },
    ])
  })

  it('ends a group with a bare ##', () => {
    expect(textToHighlights('## G\na\n##\nb')).toEqual([
      { text: 'a', group: 'G' },
      { text: 'b', group: null },
    ])
  })

  it('does not treat ## without a following space as a marker', () => {
    expect(textToHighlights('##hashtag is a bullet')).toEqual([
      { text: '##hashtag is a bullet', group: null },
    ])
  })
})

describe('highlightsToText', () => {
  it('round-trips grouped and ungrouped bullets', () => {
    const highlights = [
      { text: 'first', group: null },
      { text: 'a', group: 'Platform' },
      { text: 'b', group: 'Platform' },
      { text: 'c', group: 'Quality' },
      { text: 'last', group: null },
    ]

    expect(textToHighlights(highlightsToText(highlights))).toEqual(highlights)
  })

  it('writes plain bullets with no markers', () => {
    expect(highlightsToText([{ text: 'a', group: null }])).toBe('a')
  })
})

describe('groupHighlights', () => {
  it('gathers consecutive bullets with the same group', () => {
    expect(
      groupHighlights([
        { text: 'a', group: 'G' },
        { text: 'b', group: 'G' },
        { text: 'c', group: null },
        { text: 'd', group: 'G' },
      ]),
    ).toEqual([
      { title: 'G', bullets: ['a', 'b'] },
      { title: null, bullets: ['c'] },
      { title: 'G', bullets: ['d'] },
    ])
  })
})
