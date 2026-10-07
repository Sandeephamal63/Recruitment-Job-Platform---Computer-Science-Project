import { useId } from 'react'

interface BrandMarkProps {
  size?: number
}

/**
 * The glyph is a bar chart climbing toward a candidate dot — the product in one
 * mark. Gradients run in the rust accent family so it sits with the theme; it
 * used to be indigo, which fought the rest of the palette on every public page.
 */
export default function BrandMark({ size = 24 }: BrandMarkProps) {
  const gradientId = useId()
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      role="img"
      aria-label="Recruit logo"
    >
      <defs>
        <linearGradient id={gradientId} x1="4" y1="2" x2="20" y2="22" gradientUnits="userSpaceOnUse">
          <stop stopColor="#B4551F" />
          <stop offset="1" stopColor="#6B2709" />
        </linearGradient>
      </defs>
      <rect width="24" height="24" rx="6" fill={`url(#${gradientId})`} />
      <g fill="#fff">
        <rect x="8" y="14" width="2" height="6" rx="1" />
        <rect x="11" y="11" width="2" height="9" rx="1" />
        <rect x="14" y="8" width="2" height="12" rx="1" />
        <circle cx="15" cy="4.5" r="1.6" />
      </g>
    </svg>
  )
}
