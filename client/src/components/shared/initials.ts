const INITIALS_MAX_WORDS = 3

/**
 * Initials for a name with no image beside it.
 *
 * Shared by the company logo badge (`CompanyMark`) and the candidate avatar
 * (`AvatarImage`): both render a monogram in exactly the same situation, and
 * three separate initials implementations had already drifted apart in how many
 * letters they showed, how they treated punctuation, and what they fell back to
 * for an empty name.
 *
 * Up to three words each contribute their first letter ("Acme" -> A, "Global
 * Tech Solutions" -> GTS). Past that the middle is dropped in favour of the
 * outer words ("Alpha Beta Gamma Delta" -> AD), because a four-letter badge stops
 * being readable at the small sizes this renders at.
 */
export default function initials(name: string): string {
  const words = (name || '')
    .split(/\s+/)
    .map((word) => word.replace(/[^\p{L}\p{N}]/gu, ''))
    .filter(Boolean)

  if (words.length === 0) {
    return '?'
  }

  const picked =
    words.length > INITIALS_MAX_WORDS ? [words[0], words[words.length - 1]] : words

  return picked
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('')
    .slice(0, INITIALS_MAX_WORDS)
}
