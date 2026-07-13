// src/app/layout.tsx
import '../styles/globals.css';
import Navbar from '@/components/Navbar';
import ThemeToggle from '@/components/ThemeToggle';
import { Inter } from 'next/font/google';

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: "Jon Qamili — Fullstack Developer & Vibe Coder",
  description: "Portfolio showcasing Jon's projects, experience, and skills.",
  icons: {
    icon: '/favicon.ico',
  },
  openGraph: {
    title: "Jon Qamili — Fullstack Developer & Vibe Coder",
    description: "Portfolio showcasing Jon's projects, experience, and skills.",
    url: "https://your-portfolio.vercel.app",
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Jon Qamili Portfolio',
      },
    ],
    type: 'website',
    locale: 'en_US',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.className} data-theme="dark">
      <head>
        <link rel="preload" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" as="style" crossOrigin="anonymous" />
      </head>
      <body className="antialiased">
        <Navbar />
        <ThemeToggle />
        {children}
      </body>
    </html>
  );
}
