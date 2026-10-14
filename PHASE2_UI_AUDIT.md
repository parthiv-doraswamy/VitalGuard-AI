# VitalGuard AI — Phase 2 UI/UX changes

## Scope

This phase focuses on the agreed premium light-clinical direction while preserving the existing React page structure and simulation behaviour. No deployment was performed.

## Changes

- Shifted the global light canvas to a softer clinical neutral (`#f5f8fb`) and refined card borders/shadows.
- Reworked the dashboard hero from a dark command banner into a light clinical panel with restrained teal accents, a subtle grid and ECG motif.
- Reworked simulation controls into a light, compact control surface with accessible labels and clearer start/pause/reset affordances.
- Explicitly labelled the stream as a **demo simulation** and described the patient observations as synthetic to avoid presenting simulated data as real clinical monitoring.
- Updated the sticky header background and status label to say `Simulation running` / `Simulation paused` rather than implying a live clinical system.
- Added dark-theme overrides for the new clinical panel and retained reduced-motion handling from the existing stylesheet.
- Preserved all existing routes and component structure.

## Verification

- `npm run lint`: passed in the available environment.
- `npm test`: blocked before test execution because the archived `node_modules` does not include the Linux Rollup optional dependency `@rollup/rollup-linux-x64-gnu`.
- `npm run build`: blocked by the same missing Rollup optional dependency.
- Fresh `npm ci`: previously timed out in this environment. Run `npm ci` locally from the project directory to obtain platform-correct dependencies, then rerun tests and build.
- Browser/responsive visual QA has not been completed in a real browser. Treat the UI changes as implemented but not visually signed off.

## Next

After local test/build verification, review all six routes at desktop and mobile widths, then proceed to the FastAPI + scikit-learn model/API work. Keep the simulator visibly labelled as demo data until a backend is connected.
