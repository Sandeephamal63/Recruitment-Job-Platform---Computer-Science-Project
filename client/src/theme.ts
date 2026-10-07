import { createTheme } from '@mui/material/styles'

/**
 * Design tokens for Recruit.
 *
 * Three tiers, deliberately narrow:
 *   - `palette.grey`   neutral ramp, carries all text hierarchy and borders
 *   - `palette.primary` rust accent, reserved for primary actions and state
 *   - `palette.elevation` three-step depth ramp so cards lift off the cream
 *
 * Anything that needs a colour reads a token from here. The ad-hoc hexes that
 * used to be inlined across components (`#0b1220` headings, `#64748b` muted,
 * `#e2e8f0` borders, `#7B2D0E` everything-else) are all expressible as these.
 */

export const neutral = {
  50: '#F8F8F3',
  100: '#F1F2EA',
  200: '#E4E6DB',
  300: '#CDD1C3',
  400: '#A9AE9C',
  500: '#767C6B',
  600: '#5C6252',
  700: '#414639',
  800: '#2A2E24',
  900: '#161A12',
} as const

const accent = {
  main: '#8A3413',
  dark: '#6B2709',
  light: '#B4551F',
  faint: '#8A34130F',
  soft: '#8A341318',
  mid: '#8A341326',
  strong: '#8A341355',
} as const

const cream = '#FCFDF3'
const paper = '#FFFFFF'

/** Warm-tinted neutral used for icon tiles and inert fills. */
const tint = '#F6F1E6'

export const brand = {
  primary: accent.main,
  primaryDark: accent.dark,
  primaryLight: accent.light,
  faint: accent.faint,
  soft: accent.soft,
  mid: accent.mid,
  strong: accent.strong,
  shadow: `0 6px 16px -6px ${accent.main}66`,
  cream,
  paper,
  tint,
}

/**
 * Depth ramp. The previous `shadowCard`/`shadowSm` pair were the same string at
 * 0.04 alpha, which is invisible on the cream background — that is why every
 * card read as flat. These step up in both spread and opacity.
 */
export const elevation = {
  1: '0 1px 2px rgba(22, 26, 18, 0.05), 0 1px 3px rgba(22, 26, 18, 0.06)',
  2: '0 1px 3px rgba(22, 26, 18, 0.05), 0 10px 24px -14px rgba(22, 26, 18, 0.18)',
  3: '0 2px 6px rgba(22, 26, 18, 0.06), 0 18px 36px -18px rgba(22, 26, 18, 0.24)',
}

/** Kept for existing call sites that import the old names. */
export const shadowCard = elevation[2]
export const shadowLift = elevation[3]

/**
 * Vertical rhythm. Sections step in multiples of 16px so stacked pages share
 * one cadence instead of each page inventing its own padding.
 */
export const layout = {
  section: { xs: 4, md: 8 },
  sectionTight: { xs: 3, md: 4 },
  gutter: { xs: 3, sm: 4, md: 6 },
  blockGap: { xs: 3, md: 4 },
  cardPadding: { xs: 2.5, sm: 3 },
  /**
   * The one horizontal measure for the whole product.
   *
   * Every band on every page — navbar, hero, sections, footers, forms, listings
   * — resolves its left and right edge from these two values. `PageContainer`
   * takes them from here and exposes no `maxWidth` prop, so the width cannot be
   * varied per call site even by accident; MUI's own breakpoint scale (sm 600,
   * md 900, lg 1200, xl 1536) is deliberately bypassed rather than used, since
   * mixing those is what previously had the navbar at 1200px sitting outside
   * 1536px listings and 900px detail pages.
   */
  container: { maxWidth: 1200, px: { xs: 3, sm: 4, md: 6 } },
} as const

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: { main: accent.main, dark: accent.dark, light: accent.light, contrastText: paper },
    secondary: { main: neutral[700], dark: neutral[800], light: neutral[500], contrastText: paper },
    background: { default: cream, paper },
    text: { primary: neutral[900], secondary: neutral[500], disabled: neutral[400] },
    divider: neutral[200],
    grey: neutral,
    success: { main: '#2F7D4F', light: '#3E9C66', dark: '#215C39' },
    warning: { main: '#B4740C', light: '#D69526', dark: '#8A5607' },
    error: { main: '#B42318', light: '#D6453A', dark: '#8A1C13' },
    info: { main: neutral[600], light: neutral[500], dark: neutral[800] },
  },
  shape: { borderRadius: 10 },
  spacing: 8,
  typography: {
    fontFamily: [
      'Inter',
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: { fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1.1, fontSize: 'clamp(2rem, 4.2vw, 3rem)' },
    h2: { fontWeight: 700, letterSpacing: '-0.02em', lineHeight: 1.2, fontSize: 'clamp(1.5rem, 2.4vw, 1.875rem)' },
    h3: { fontWeight: 600, letterSpacing: '-0.015em', lineHeight: 1.3, fontSize: '1.1875rem' },
    h4: { fontWeight: 700, letterSpacing: '-0.022em', lineHeight: 1.25, fontSize: 'clamp(1.375rem, 2.4vw, 1.875rem)' },
    h5: { fontWeight: 600, letterSpacing: '-0.01em', lineHeight: 1.35, fontSize: '1.0625rem' },
    h6: { fontWeight: 600, letterSpacing: '-0.005em', lineHeight: 1.4, fontSize: '0.9375rem' },
    subtitle1: { fontWeight: 600, fontSize: '0.9375rem', lineHeight: 1.5 },
    subtitle2: { fontWeight: 600, fontSize: '0.8125rem', lineHeight: 1.5 },
    body1: { fontSize: '1rem', lineHeight: 1.65, fontWeight: 400 },
    body2: { fontSize: '0.875rem', lineHeight: 1.6, fontWeight: 400 },
    button: { textTransform: 'none', fontWeight: 600, letterSpacing: 0, fontSize: '0.875rem' },
    caption: { fontSize: '0.75rem', lineHeight: 1.5, fontWeight: 500, letterSpacing: '0.01em' },
    overline: { fontSize: '0.6875rem', lineHeight: 1.6, fontWeight: 700, letterSpacing: '0.09em' },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        html: { scrollBehavior: 'smooth' },
        body: {
          backgroundColor: cream,
          WebkitFontSmoothing: 'antialiased',
          MozOsxFontSmoothing: 'grayscale',
        },
        '::selection': { backgroundColor: accent.soft },
        '*:focus-visible': { outline: `2px solid ${accent.main}`, outlineOffset: 2 },
        /**
         * Guard rail for the shared horizontal measure.
         *
         * `PageContainer` is the mechanism and every band on every page uses it.
         * This catches the case where someone reaches for MUI's `Container`
         * directly, which defaults to 16px of inline padding and would put that
         * element 8–32px outside everything beside it. Declared here rather than
         * in `MuiContainer.styleOverrides` because that slot's typing rejects a
         * responsive value object; the breakpoint numbers mirror MUI's
         * sm/md, which is what `layout.gutter` is expressed in.
         */
        '.MuiContainer-root': {
          paddingLeft: '24px',
          paddingRight: '24px',
          '@media (min-width:600px)': { paddingLeft: '32px', paddingRight: '32px' },
          '@media (min-width:900px)': { paddingLeft: '48px', paddingRight: '48px' },
        },
      },
    },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          borderRadius: 8,
          paddingInline: 16,
          paddingBlock: 7,
          transition: 'background-color .16s ease, border-color .16s ease, color .16s ease, box-shadow .16s ease, transform .1s ease',
          '&:active': { transform: 'translateY(1px)' },
          '& .MuiButton-startIcon svg, & .MuiButton-endIcon svg': { fontSize: '1.125em' },
        },
        containedPrimary: {
          boxShadow: '0 1px 2px rgba(138, 52, 19, 0.28)',
          '&:hover': { backgroundColor: accent.dark, boxShadow: '0 4px 12px -4px rgba(138, 52, 19, 0.5)' },
          '&.Mui-disabled': { backgroundColor: neutral[300], color: paper, boxShadow: 'none' },
        },
        outlined: {
          borderColor: neutral[300],
          color: neutral[800],
          '&:hover': { borderColor: neutral[400], backgroundColor: neutral[50] },
          '&.Mui-disabled': { borderColor: neutral[200], color: neutral[400], backgroundColor: 'transparent' },
        },
        outlinedPrimary: {
          borderWidth: 1,
          '&:hover': { borderWidth: 1, backgroundColor: accent.faint },
        },
        outlinedSecondary: {
          borderWidth: 1,
          '&:hover': { borderWidth: 1, backgroundColor: neutral[100] },
        },
        sizeLarge: { paddingBlock: 10, paddingInline: 22, fontSize: '0.9375rem' },
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          backgroundColor: paper,
          transition: 'border-color .16s ease, box-shadow .16s ease',
          '& .MuiOutlinedInput-notchedOutline': { borderColor: neutral[300] },
          '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: neutral[400] },
          '&.Mui-focused': { boxShadow: `0 0 0 3px ${accent.soft}` },
          '&.Mui-error:hover .MuiOutlinedInput-notchedOutline': { borderColor: '#D6453A' },
          '&.Mui-disabled': { backgroundColor: neutral[50], color: neutral[400] },
        },
        input: {
          '&:not(.MuiInputBase-inputSizeSmall)': { paddingBlock: 11 },
        },
      },
    },
    MuiInputBase: {
      styleOverrides: {
        input: {
          '&:not(.MuiInputBase-inputSizeSmall)': { paddingBlock: 11 },
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: { root: { color: neutral[500], fontWeight: 500 } },
    },
    MuiFormHelperText: {
      styleOverrides: { root: { marginInlineStart: 2, marginBlockStart: 6, fontSize: '0.75rem' } },
    },
    MuiCard: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          borderRadius: 3,
          border: `1px solid ${neutral[200]}`,
          boxShadow: elevation[2],
          backgroundColor: paper,
          transition: 'box-shadow .18s ease, border-color .18s ease, transform .18s ease',
          '&:hover': { boxShadow: elevation[3], borderColor: neutral[300] },
        },
      },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: { backgroundImage: 'none' },
        rounded: { borderRadius: 3 },
        outlined: { borderColor: neutral[200] },
      },
    },
    MuiAppBar: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          backgroundColor: paper,
          color: neutral[900],
          borderBottom: `1px solid ${neutral[200]}`,
          boxShadow: elevation[1],
        },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          borderRadius: 999,
          paddingBlock: 9,
          borderColor: neutral[300],
          color: neutral[600],
          transition: 'background-color .16s ease, color .16s ease, box-shadow .16s ease',
          '&:hover': { backgroundColor: neutral[100] },
          '&.Mui-selected': {
            backgroundColor: paper,
            color: accent.main,
            boxShadow: elevation[1],
            '&:hover': { backgroundColor: paper },
          },
          '&.Mui-disabled': { color: neutral[400], backgroundColor: 'transparent' },
        },
      },
    },
    MuiAlert: {
      styleOverrides: { root: { borderRadius: 3, alignItems: 'center' } },
    },
    MuiChip: {
      styleOverrides: {
        root: { fontWeight: 600, borderRadius: 999, height: 26 },
        outlined: { borderColor: neutral[300], color: neutral[700] },
      },
    },
    MuiLink: {
      defaultProps: { underline: 'hover' },
      styleOverrides: {
        root: { fontWeight: 600, color: accent.main, '&:hover': { color: accent.dark } },
      },
    },
    MuiTooltip: {
      styleOverrides: { tooltip: { backgroundColor: neutral[900], fontSize: 12, borderRadius: 8, paddingInline: 10 } },
    },
    MuiAvatar: { styleOverrides: { root: { fontWeight: 700 } } },
    MuiIconButton: {
      styleOverrides: {
        root: {
          transition: 'background-color .16s ease, color .16s ease',
          '&:hover': { backgroundColor: neutral[100] },
        },
      },
    },
    MuiDivider: { styleOverrides: { root: { borderColor: neutral[200] } } },
    MuiTableCell: {
      styleOverrides: {
        head: { fontWeight: 600, color: neutral[500], fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.06em' },
      },
    },
    MuiTableRow: { styleOverrides: { root: { '&:last-child td': { borderBottom: 'none' } } } },
    MuiMenu: {
      styleOverrides: { paper: { borderRadius: 3, border: `1px solid ${neutral[200]}`, boxShadow: elevation[3] } },
    },
    MuiMenuItem: { styleOverrides: { root: { borderRadius: 1.5, my: 0.5, minHeight: 40 } } },
    MuiDrawer: { styleOverrides: { paper: { borderRight: `1px solid ${neutral[200]}`, boxShadow: elevation[3] } } },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 2,
          transition: 'background-color .16s ease',
          '&.Mui-selected': {
            backgroundColor: accent.faint,
            '&:hover': { backgroundColor: accent.soft },
            '& .MuiListItemIcon-root': { color: accent.main },
          },
        },
      },
    },
    MuiListItemIcon: { styleOverrides: { root: { color: neutral[500], minWidth: 40 } } },
    MuiBreadcrumbs: { styleOverrides: { separator: { color: neutral[400] }, li: { fontSize: '0.8125rem' } } },
    MuiTabs: { styleOverrides: { indicator: { backgroundColor: accent.main, height: 2, borderRadius: 1 } } },
    MuiTab: {
      styleOverrides: {
        root: { textTransform: 'none', fontWeight: 600, fontSize: '0.875rem', minHeight: 48, '&.Mui-selected': { color: accent.main } },
      },
    },
    MuiPagination: {
      styleOverrides: {
        root: { '& .MuiPaginationItem-root': { borderRadius: 2, fontWeight: 600 } },
      },
    },
  },
})

export default theme
