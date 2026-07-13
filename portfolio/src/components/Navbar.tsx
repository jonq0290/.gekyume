'use client';

import Link from 'next/link';
import { useState } from 'react';

export default function Navbar() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <nav className="fixed w-full bg-dark bg-opacity-80 backdrop-blur-sm text-white flex items-center justify-between px-6 py-4 z-50">
      <div className="text-2xl font-bold tracking-wider">Jon Q</div>
      <ul className="hidden md:flex space-x-6">
        <li><Link href="#hero" className="hover:text-accent-blue transition">Home</Link></li>
        <li><Link href="#about" className="hover:text-accent-blue transition">About</Link></li>
        <li><Link href="#projects" className="hover:text-accent-blue transition">Projects</Link></li>
        <li><Link href="#contact" className="hover:text-accent-blue transition">Contact</Link></li>
      </ul>
      <button className="md:hidden" onClick={() => setMenuOpen(!menuOpen)} aria-label="Menu">
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={menuOpen ? 'M6 18L18 6M6 6l12 12' : 'M4 6h16M4 12h16M4 18h16'} /></svg>
      </button>
      {menuOpen && (
        <ul className="absolute top-full left-0 w-full bg-dark bg-opacity-90 backdrop-blur-sm flex flex-col items-center space-y-4 py-4 md:hidden">
          <li><Link href="#hero" onClick={() => setMenuOpen(false)}>Home</Link></li>
          <li><Link href="#about" onClick={() => setMenuOpen(false)}>About</Link></li>
          <li><Link href="#projects" onClick={() => setMenuOpen(false)}>Projects</Link></li>
          <li><Link href="#contact" onClick={() => setMenuOpen(false)}>Contact</Link></li>
        </ul>
      )}
    </nav>
  );
}
