# Vendored assets

Inlined into `out/dashboard.html` at build time so the dashboard has no external
dependencies and renders identically offline.

| Asset | Version | License |
|---|---|---|
| `chart.umd.min.js` — Chart.js | 4.5.1 | MIT |
| `fonts/bricolage-grotesque-*` | via @fontsource 5.2.10 | SIL Open Font License 1.1 |
| `fonts/source-serif-4-*` | via @fontsource 5.2.9 | SIL Open Font License 1.1 |
| `fonts/ibm-plex-mono-*` | via @fontsource 5.2.7 | SIL Open Font License 1.1 |

Only the latin subset and the weights actually used are included (~350kb total).
To refresh: `npm pack chart.js @fontsource/bricolage-grotesque @fontsource/source-serif-4 @fontsource/ibm-plex-mono`
