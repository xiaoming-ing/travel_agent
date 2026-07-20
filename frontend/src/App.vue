<template>
  <router-view />
</template>

<style>
/* 全局样式：不加 scoped，作用于整个应用 */
:root {
  --color-paper: #f7f4ee;
  --color-surface: #ffffff;
  --color-ink: #1f2933;
  --color-note: #5b6770;
  --color-muted: #8a9188;
  --color-signal: #c44e2d;
  --color-signal-dark: #9f3e24;
  --color-route: #1f6f78;
  --color-ticket: #d8c7a3;
  --color-border: #e7e2d8;
  --color-soft: #f1ece3;
  --radius-card: 8px;
  --shadow-soft: 0 10px 28px rgba(31, 41, 51, 0.06);
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: "Inter", -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Microsoft YaHei", sans-serif;
  background: var(--color-paper);
  min-height: 100vh;
  color: var(--color-ink);
  font-variant-numeric: tabular-nums;
}

button,
input,
select,
textarea {
  font: inherit;
}

button {
  transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease, opacity 0.16s ease;
}

@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    scroll-behavior: auto !important;
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
}
</style>
