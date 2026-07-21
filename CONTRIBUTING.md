# Contributing

Thanks for wanting to help! A few ground rules keep this project what it is:

- **Single file, no build step.** The whole app is `index.html` — open it and
  it works. PRs that introduce bundlers, frameworks, package managers, or
  split the file into modules will be declined, even good ones. This is a
  deliberate choice so that non-developers can host and tweak it.
- **Vanilla JS only, no dependencies.**
- **Keep diffs small and focused.** One fix or feature per PR; don't reformat
  code you aren't changing.
- **User-facing text goes through `STRINGS`.** Add both English and German
  where you can (machine translation for German is fine, mark it in the PR).
- **Test by opening the page.** Serve the folder (`python -m http.server`)
  and click through: grid, player, timeline comments, likes/tags, filters,
  stats. There is no test suite — your eyes are the test suite.

New language packs for `STRINGS`, accessibility fixes, and bug fixes are
especially welcome.
