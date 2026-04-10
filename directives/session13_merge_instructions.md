# How to Merge the Landing Page Changes Into Your Local Repo

> **Who is this for:** A developer who has the Igloo repo cloned locally and needs to pull in the `landing-redesign` branch changes.
>
> **What this does:** Brings all the landing page work (legal pages, pricing update, design, assets) into your local `main` branch.
>
> **Time required:** ~10 minutes.

---

## Prerequisites

- You have the Igloo repo cloned on your machine
- You have `git` installed
- You have `node` (v18+) and `npm` installed
- You have terminal/command line access

---

## Step-by-Step Instructions

### Step 1: Open your terminal and navigate to the igloo repo

```bash
cd path/to/your/igloo
```

Replace `path/to/your/igloo` with the actual path where you cloned the repo. For example:
```bash
cd ~/Desktop/igloo
```

### Step 2: Make sure you have no uncommitted changes

```bash
git status
```

If you see files listed under "Changes not staged" or "Untracked files" that you care about, commit or stash them first:

```bash
# Option A: Commit your current work
git add -A
git commit -m "Save my current work before merge"

# Option B: Stash (temporarily set aside) your changes
git stash
```

If `git status` says "nothing to commit, working tree clean" — you're good, move on.

### Step 3: Switch to the main branch

```bash
git checkout main
```

You should see: `Switched to branch 'main'`

### Step 4: Pull the latest from GitHub

```bash
git pull origin main
```

This makes sure your `main` branch is up to date with what's on GitHub.

### Step 5: Fetch the landing-redesign branch

```bash
git fetch origin landing-redesign
```

This downloads the branch but doesn't change any of your files yet.

### Step 6: Merge the landing-redesign branch into main

```bash
git merge origin/landing-redesign
```

**What happens now:**
- If it says `Already up to date` — the changes are already in main (someone already merged it).
- If it lists files and says `Merge made by...` — success! The changes are now in your local main.
- If it says `CONFLICT` — see the "Handling Merge Conflicts" section below.

### Step 7: Install dependencies (just in case)

```bash
cd app
npm install
```

This ensures your `node_modules` is up to date. Even though no new dependencies were added in this session, it's good practice.

### Step 8: Verify the build works

```bash
# Type check (must show no errors)
./node_modules/.bin/tsc --noEmit

# Full build (must succeed)
npm run build
```

**Important:** Do NOT use `npx tsc` — it grabs the wrong package. Always use `./node_modules/.bin/tsc`.

If the build fails because of Google Fonts (error mentions "Failed to fetch Inter" or "Failed to fetch Geist Mono"), that's a network issue, not a code issue. Make sure you have internet access and try again.

### Step 9: Test locally

```bash
npm run dev
```

Open your browser to `http://localhost:3000` and check:

| URL | What you should see |
|-----|--------------------|
| `http://localhost:3000/` | Landing page with pricing showing "$14.99 for 2 videos" |
| `http://localhost:3000/privacy` | Privacy policy page with dark theme, amber accent |
| `http://localhost:3000/terms` | Terms of service page |
| `http://localhost:3000/refund` | Refund policy page with amber callout box |
| `http://localhost:3000/contact` | Contact page with email callout box |
| `http://localhost:3000/create` | Should still work (Razorpay checkout) |
| `http://localhost:3000/admin` | Should still work (requires auth) |

**Tip:** If videos don't play, try incognito mode (`Cmd+Shift+N` on Mac, `Ctrl+Shift+N` on Windows). Some browser extensions block video playback.

### Step 10: Push merged main to GitHub

```bash
cd ..  # go back to igloo root (if you're still in app/)
git push origin main
```

Done! The changes are now on GitHub's main branch.

---

## Handling Merge Conflicts

If Step 6 shows `CONFLICT`, it means someone else changed the same file. Here's what to do:

### See which files have conflicts
```bash
git status
```

Files listed under "both modified" have conflicts.

### Open the conflicting file

Look for sections that look like this:
```
<<<<<<< HEAD
your current code
=======
the landing-redesign code
>>>>>>> origin/landing-redesign
```

### Decide which version to keep

- **If the conflict is in `globals.css`:** Keep BOTH versions. The landing-redesign code adds new styles at the end — it should not replace your existing styles.
- **If the conflict is in `proxy.ts`:** Make sure the final file has ALL the public routes (including `/privacy`, `/terms`, `/refund`, `/contact`).
- **If the conflict is in any file under `app/src/components/`:** The landing-redesign version is likely correct since these are new files.

### After resolving, mark as resolved and commit

```bash
git add the-conflicting-file.tsx
git commit -m "Merge landing-redesign into main, resolve conflicts"
```

Then continue from Step 7.

---

## If Something Goes Wrong

### "I merged but everything looks broken"

Undo the merge:
```bash
git merge --abort
```

This only works if you haven't committed yet. If you already committed, contact the team before doing anything else.

### "I accidentally deleted files"

The old static HTML files (`privacy.html`, `terms.html`, etc.) were intentionally deleted. They've been replaced by Next.js route pages. This is expected.

### "Legal pages redirect to sign-in instead of showing content"

Check `src/proxy.ts`. It must have these 4 routes in the `isPublicRoute` array:
```ts
"/privacy",
"/terms",
"/refund",
"/contact",
```

### "Build fails with TypeScript errors"

Run this exact command (not `npx tsc`):
```bash
./node_modules/.bin/tsc --noEmit
```

If errors appear in files you didn't touch (like `api/` or `lib/`), don't fix them — report to the team.

### "I want to undo everything and start over"

```bash
git checkout main
git reset --hard origin/main
```

**Warning:** This deletes ALL your local uncommitted changes. Only use as a last resort.

---

## What Changed (Summary)

For the full breakdown, see `directives/session13_integration_guide.md` and `directives/session13_impact_analysis.md` in the repo.

**Short version:**
- 4 new legal pages (Privacy, Terms, Refund, Contact) as Next.js routes
- Legal pages styled to match the landing page design
- Pricing updated to bundle-first display ($14.99 for 2 videos)
- Footer links updated from `.html` to clean paths
- Clerk middleware updated to make legal pages publicly accessible
- Zero new dependencies added
- Zero changes to auth, payments, database, or admin code
