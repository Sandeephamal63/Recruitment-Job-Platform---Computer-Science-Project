import { Box } from '@mui/material'
import { Outlet } from 'react-router-dom'
import Navbar from '@/components/public/Navbar'
import Footer from '@/components/public/Footer'
import { brand } from '@/theme'

/** Public shell. Owns the navbar and footer for every unauthenticated route —
 *  pages render body content only. */
export default function PublicLayout() {
  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: brand.cream,
      }}
    >
      <Navbar />
      <Box component="main" sx={{ flexGrow: 1, width: '100%' }}>
        <Outlet />
      </Box>
      <Footer />
    </Box>
  )
}
