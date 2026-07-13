import Link from 'next/link';

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 flex flex-col items-center px-4 md:px-8 py-20 selection:bg-teal-500/30 selection:text-teal-300 transition-colors duration-300">
      {/* Glow Effects */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-full max-w-7xl h-[500px] bg-gradient-to-b from-teal-500/10 via-emerald-500/5 to-transparent blur-3xl pointer-events-none -z-10" />

      {/* Hero Section */}
      <section id="hero" className="w-full max-w-4xl py-24 md:py-36 flex flex-col items-start justify-center gap-6">
        <span className="font-mono text-teal-600 dark:text-teal-400 text-sm md:text-base tracking-widest font-medium">Hi, my name is</span>
        <h1 className="text-4xl md:text-7xl font-extrabold tracking-tight text-slate-900 dark:text-white">
          Jon Qamili.
        </h1>
        <p className="text-2xl md:text-4xl font-semibold text-slate-700 dark:text-slate-400 max-w-2xl">
          I'm a <span className="text-teal-600 dark:text-teal-400">Vibe Coder</span> specialized in building <span className="text-emerald-600 dark:text-emerald-400">AI Agents</span>.
        </p>
        <p className="text-slate-600 dark:text-slate-400 max-w-xl text-base md:text-lg leading-relaxed">
          I build high-fidelity web experiences and orchestrate autonomous systems. By merging the speed of vibe coding with agentic automation, I deliver polished solutions at modern speed.
        </p>
        <div className="mt-8">
          <Link
            href="#projects"
            className="px-6 py-3 border border-teal-600 dark:border-teal-400 text-teal-600 dark:text-teal-400 font-mono text-sm rounded hover:bg-teal-50 dark:hover:bg-teal-950/30 hover:-translate-y-1 transition duration-300 inline-block shadow-lg hover:shadow-teal-500/20"
          >
            Explore Projects
          </Link>
        </div>
      </section>

      {/* About Section */}
      <section id="about" className="w-full max-w-4xl py-24 border-t border-slate-200 dark:border-slate-900 flex flex-col gap-8">
        <h2 className="text-2xl md:text-3xl font-bold flex items-center gap-3 text-slate-900 dark:text-white">
          <span className="font-mono text-teal-600 dark:text-teal-400 text-lg">//</span> About Me
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-10 items-start">
          <div className="md:col-span-3 flex flex-col gap-4 text-slate-600 dark:text-slate-400 text-base md:text-lg leading-relaxed">
            <p>
              I thrive at the intersection of developer experience and artificial intelligence. My philosophy revolves around vibe coding: expressing design intent clearly and allowing AI agents to handle the mechanics, enabling extreme velocity.
            </p>
            <p>
              Beyond building web interfaces, I research agent-to-agent communication networks and direct integration patterns.
            </p>
            <p>Here are some of the tools, frameworks, and skills I leverage daily:</p>
            <ul className="grid grid-cols-2 gap-2 font-mono text-sm text-teal-600 dark:text-teal-300 mt-2">
              <li className="flex items-center gap-2">
                <span className="text-teal-500">▹</span> Vibe Coding
              </li>
              <li className="flex items-center gap-2">
                <span className="text-teal-500">▹</span> AI Agents / LLMs
              </li>
              <li className="flex items-center gap-2">
                <span className="text-teal-500">▹</span> Next.js / React
              </li>
              <li className="flex items-center gap-2">
                <span className="text-teal-500">▹</span> TypeScript
              </li>
              <li className="flex items-center gap-2">
                <span className="text-teal-500">▹</span> Python
              </li>
              <li className="flex items-center gap-2">
                <span className="text-teal-500">▹</span> Git &amp; CI/CD
              </li>
            </ul>
          </div>
          <div className="md:col-span-2 flex justify-center">
            <div className="relative group w-64 h-64 border border-slate-200 dark:border-teal-500/30 bg-white dark:bg-slate-900/50 rounded-2xl overflow-hidden shadow-2xl flex items-center justify-center backdrop-blur-sm group-hover:border-teal-500 transition-colors duration-300">
              <div className="absolute inset-0 bg-gradient-to-tr from-teal-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              <div className="absolute w-44 h-44 rounded-full border border-dashed border-teal-600/20 dark:border-teal-500/20 group-hover:border-teal-500/40 animate-[spin_25s_linear_infinite] transition-colors" />
              <span className="font-mono text-4xl text-teal-600 dark:text-teal-400 font-bold group-hover:scale-110 transition-transform duration-300">&lt;JQ/&gt;</span>
            </div>
          </div>
        </div>
      </section>

      {/* Projects Section */}
      <section id="projects" className="w-full max-w-4xl py-24 border-t border-slate-200 dark:border-slate-900 flex flex-col gap-8">
        <h2 className="text-2xl md:text-3xl font-bold flex items-center gap-3 text-slate-900 dark:text-white">
          <span className="font-mono text-teal-600 dark:text-teal-400 text-lg">//</span> Featured Projects
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Vibe Crafted App card */}
          <article className="p-6 rounded-xl border border-slate-200 dark:border-slate-900 bg-white dark:bg-slate-900/40 hover:bg-slate-100 dark:hover:bg-slate-900/60 hover:border-teal-500/30 transition-all duration-300 flex flex-col justify-between group shadow-xl">
            <div>
              <div className="flex justify-between items-center mb-6">
                <span className="text-3xl">🌐</span>
                <a
                  href="https://heartfelt-cucurucho-950946.netlify.app/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-500 hover:text-teal-600 dark:text-slate-400 dark:hover:text-teal-400 transition"
                  aria-label="Live Demo Link"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              </div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2 group-hover:text-teal-600 dark:group-hover:text-teal-300 transition-colors">
                Vibe Crafted App
              </h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
                An interactive and responsive web application designed, scaffolded, and deployed using vibe coding workflows.
              </p>
            </div>
            <div className="pt-4 mt-auto">
              <a
                href="https://heartfelt-cucurucho-950946.netlify.app/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-teal-600 dark:text-teal-400 hover:text-teal-700 dark:hover:text-teal-300 font-mono text-xs font-semibold tracking-wider uppercase flex items-center gap-1"
              >
                Live Demo <span>↗</span>
              </a>
            </div>
          </article>

          {/* Project 2 card */}
          <article className="p-6 rounded-xl border border-slate-200 dark:border-slate-900 bg-white dark:bg-slate-900/40 hover:bg-slate-100 dark:hover:bg-slate-900/60 hover:border-teal-500/30 transition-all duration-300 flex flex-col justify-between group shadow-xl">
            <div>
              <div className="flex justify-between items-center mb-6">
                <span className="text-3xl">📂</span>
                <a
                  href="https://github.com/jonq0290"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-500 hover:text-teal-600 dark:text-slate-400 dark:hover:text-teal-400 transition"
                  aria-label="GitHub Repository"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
                  </svg>
                </a>
              </div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2 group-hover:text-teal-600 dark:group-hover:text-teal-300 transition-colors">
                Agent Coordinator
              </h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
                An experimental orchestration layer designed to handle communication protocols between multiple localized AI Agents.
              </p>
            </div>
            <div className="pt-4 mt-auto">
              <span className="text-slate-500 font-mono text-xs">Python · LLMs</span>
            </div>
          </article>

          {/* Project 3 card */}
          <article className="p-6 rounded-xl border border-slate-200 dark:border-slate-900 bg-white dark:bg-slate-900/40 hover:bg-slate-100 dark:hover:bg-slate-900/60 hover:border-teal-500/30 transition-all duration-300 flex flex-col justify-between group shadow-xl">
            <div>
              <div className="flex justify-between items-center mb-6">
                <span className="text-3xl">📂</span>
                <a
                  href="https://github.com/jonq0290"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-slate-500 hover:text-teal-600 dark:text-slate-400 dark:hover:text-teal-400 transition"
                  aria-label="GitHub Repository"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
                  </svg>
                </a>
              </div>
              <h3 className="text-xl font-bold text-slate-900 dark:text-white mb-2 group-hover:text-teal-600 dark:group-hover:text-teal-300 transition-colors">
                Vibe Engine
              </h3>
              <p className="text-slate-600 dark:text-slate-400 text-sm leading-relaxed mb-4">
                A blazing fast parser and automation utility suite for Markdown-based sites and developer docs.
              </p>
            </div>
            <div className="pt-4 mt-auto">
              <span className="text-slate-500 font-mono text-xs">TypeScript · Node</span>
            </div>
          </article>
        </div>
      </section>

      {/* Contact Section */}
      <section id="contact" className="w-full max-w-4xl py-24 border-t border-slate-200 dark:border-slate-900 flex flex-col items-center text-center gap-6">
        <h2 className="text-2xl md:text-3xl font-bold flex items-center gap-3 text-slate-900 dark:text-white">
          <span className="font-mono text-teal-600 dark:text-teal-400 text-lg">//</span> Get In Touch
        </h2>
        <p className="text-slate-600 dark:text-slate-400 max-w-md text-base md:text-lg leading-relaxed">
          I am currently open to collaborations, projects, or just chatting about vibe coding and agents. Drop me a line!
        </p>
        <a
          href="mailto:jon@example.com"
          className="mt-4 px-8 py-4 bg-teal-600 hover:bg-teal-500 dark:bg-teal-400 dark:hover:bg-teal-300 text-white dark:text-slate-950 font-bold rounded shadow-lg hover:shadow-teal-500/20 hover:-translate-y-1 transition duration-300"
        >
          Email Me
        </a>
      </section>

      {/* Footer */}
      <footer className="w-full max-w-4xl pt-16 pb-8 border-t border-slate-200 dark:border-slate-900 flex flex-col md:flex-row justify-between items-center gap-4 text-slate-500 text-sm font-mono">
        <div className="flex gap-6">
          <a href="https://github.com/jonq0290" target="_blank" rel="noopener noreferrer" className="hover:text-teal-600 dark:hover:text-teal-400 transition">
            GitHub
          </a>
          <a href="https://www.linkedin.com/in/jon-qamili-02558234a/" target="_blank" rel="noopener noreferrer" className="hover:text-teal-600 dark:hover:text-teal-400 transition">
            LinkedIn
          </a>
        </div>
        <p>Built by Jon &copy; 2026</p>
      </footer>
    </main>
  );
}
