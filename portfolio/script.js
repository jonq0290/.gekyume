/* -------------------------------------------------
   Jon's Portfolio - Modern Interactive JS Features
   ------------------------------------------------- */

document.addEventListener('DOMContentLoaded', () => {
  const root = document.documentElement;
  const themeToggle = document.getElementById('theme-toggle');

  // Load theme preference from localStorage or default to system theme
  const getThemePreference = () => {
    const localTheme = localStorage.getItem('theme');
    if (localTheme) return localTheme;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  };

  const applyTheme = (theme) => {
    root.setAttribute('data-theme', theme);
    themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
  };

  let currentTheme = getThemePreference();
  applyTheme(currentTheme);

  // Theme toggle click handler
  themeToggle.addEventListener('click', () => {
    currentTheme = currentTheme === 'dark' ? 'light' : 'dark';
    applyTheme(currentTheme);
    localStorage.setItem('theme', currentTheme);
  });

  // Dynamic Scroll Indicator & Sticky Nav
  const header = document.querySelector('header');
  window.addEventListener('scroll', () => {
    if (window.scrollY > 50) {
      header.style.boxShadow = '0 10px 30px rgba(0, 0, 0, 0.1)';
      header.style.padding = '5px 0';
    } else {
      header.style.boxShadow = 'none';
      header.style.padding = '0';
    }
  });

  // Micro-interactivity for Project Cards
  const cards = document.querySelectorAll('.project-card');
  cards.forEach(card => {
    card.addEventListener('mouseenter', () => {
      card.style.transform = 'translateY(-10px) scale(1.02)';
    });
    card.addEventListener('mouseleave', () => {
      card.style.transform = 'translateY(0) scale(1)';
    });
  });
});
