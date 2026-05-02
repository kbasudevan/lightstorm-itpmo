# ITPMO — IT Project Management Office

**Live App:** https://lightstorm-itpmo.azurewebsites.net

A web application for the Enterprise Architecture & Product Engineering team to track, manage, and report on all IT projects across strategic business domains.

---

## How the Development & Deployment Workflow Works

Every time you want to make a change to the website — whether it's a bug fix, a new feature, or a content update — you follow the same five-step process below. This ensures all changes are reviewed before they go live, and deployment to Azure happens automatically.

```
                        YOUR LAPTOP                          GITHUB                        AZURE CLOUD
                       ┌──────────────────────┐         ┌──────────────┐              ┌────────────────────┐
                       │                      │         │              │              │                    │
  STEP 1               │  main branch         │         │  main branch │              │   Live Website     │
  ─────────────────►   │  ┌───────────────┐   │  ──►    │  ┌─────────┐ │              │                    │
  Create a new         │  │ my-new-branch │   │         │  │  main   │ │              │  lightstorm-itpmo  │
  branch from main     │  └───────────────┘   │         │  └─────────┘ │              │  .azurewebsites    │
                       │         │            │         │              │              │  .net              │
  STEP 2               │         ▼            │         │              │              │                    │
  ─────────────────►   │  Make your changes   │         │              │              └────────────────────┘
  Edit the code        │  (edit files)        │         │              │                        ▲
                       │         │            │         │              │                        │
  STEP 3               │         ▼            │         │              │                        │
  ─────────────────►   │  git push            │ ──────► │  your branch │                        │
  Push branch          │  origin my-branch    │         │  appears on  │                        │
  to GitHub            │                      │         │  GitHub      │                        │
                       └──────────────────────┘         │      │       │                        │
                                                         │      ▼       │                        │
  STEP 4                                                 │  Open a PR   │                        │
  ─────────────────────────────────────────────────►     │  (Pull Req.) │                        │
  Create a Pull Request                                  │  Review code │                        │
  on GitHub                                              │      │       │                        │
                                                         │      ▼       │                        │
  STEP 5                                                 │   Merge PR   │                        │
  ─────────────────────────────────────────────────►     │  into main   │                        │
  Merge the PR                                           │      │       │                        │
                                                         │      ▼       │                        │
                                                         │  🤖 GitHub   │                        │
                                                         │  Actions CI/ │                        │
                                                         │  CD pipeline │                        │
                                                         │  starts AUTO │                        │
                                                         │  MATICALLY   │                        │
                                                         │      │       │                        │
                                                         │  ✅ Build &  │                        │
                                                         │  Validate    │                        │
                                                         │  (checks for │                        │
                                                         │  errors)     │                        │
                                                         │      │       │                        │
                                                         │  🚀 Deploy   │ ──────────────────────►│
                                                         │  to Azure    │                        │
                                                         └──────────────┘                        │
                                                                               Website updated!  │
                                                                               ◄──────────────────┘
```

---

## Step-by-Step Guide

### Step 1 — Create a New Branch

Think of a **branch** as your own personal copy of the website code where you can make changes safely, without affecting the live website.

Open your terminal in the project folder and run:

```bash
git checkout main          # make sure you start from the latest version
git pull origin main       # download the latest changes from GitHub
git checkout -b my-feature # create your own branch (replace "my-feature" with a short name)
```

> **Layman tip:** A branch is like making a photocopy of a document. You write on the copy, not the original. If you make a mistake, the original is safe.

---

### Step 2 — Make Your Changes

Open and edit the files you want to change using any code editor (e.g., VS Code).

Once you're done editing, save your changes into git:

```bash
git add .                              # tell git "these are the files I changed"
git commit -m "Describe your change"   # save a snapshot with a short description
```

> **Example commit message:** `"Add new field to project form"` or `"Fix login page typo"`

---

### Step 3 — Push Your Branch to GitHub

Upload your branch (and its changes) to GitHub so others can see it:

```bash
git push origin my-feature
```

Your branch is now visible on GitHub at:
`https://github.com/kbasudevan/lightstorm-itpmo`

---

### Step 4 — Create a Pull Request (PR)

A **Pull Request** is a formal request to merge your changes into the main codebase. It lets teammates review your code before it goes live.

1. Go to https://github.com/kbasudevan/lightstorm-itpmo
2. You will see a yellow banner: **"Compare & pull request"** — click it
3. Write a short title and description of what you changed
4. Click **"Create pull request"**

> **Layman tip:** A Pull Request is like submitting a document for approval before it gets published. Someone reviews it, and if it looks good, they approve it.

---

### Step 5 — Review & Merge the PR

Once the PR is created:

1. Review the changes shown on the PR page (green = added, red = removed)
2. If everything looks correct, click **"Merge pull request"**
3. Click **"Confirm merge"**

That's it — your changes are now part of the main codebase.

---

### Step 6 — Automatic Deployment to Azure (Nothing to do!)

The moment you merge the PR, the **CI/CD pipeline starts automatically**. You do not need to do anything.

Here is what happens behind the scenes:

| Stage | What it does | Time taken |
|-------|-------------|------------|
| ✅ Build & Validate | Checks that the code has no syntax errors and no passwords accidentally committed | ~10 seconds |
| 🚀 Deploy to Azure | Packages the code into a zip file and uploads it to Azure App Service | ~90 seconds |
| 🔍 Health Check | Visits the live website to confirm it is responding correctly | ~25 seconds |

**Total time from merge to live: approximately 2 minutes.**

You can watch the pipeline run at:
`https://github.com/kbasudevan/lightstorm-itpmo/actions`

If the pipeline shows a green ✅, the deployment succeeded.
If it shows a red ❌, something went wrong — click on the run to see the error logs.

---

## Full Workflow at a Glance

```
  You                  GitHub                  GitHub Actions          Azure
  ─────                ──────                  ──────────────          ─────
  1. git checkout -b   
     my-branch         
  
  2. Edit code         
     git commit        
  
  3. git push   ──────► Branch on GitHub
  
  4. Open PR    ──────► Pull Request created
  
  5. Merge PR   ──────► Code merged to main ──► Pipeline starts ──────► App deployed
                                               │                         │
                                               ├─ ✅ Syntax check        │
                                               ├─ ✅ Secrets check       │
                                               ├─ 🚀 Zip & upload        │
                                               └─ 🔍 Health check ──────► Live!
```

---

## Quick Reference — Commands You Need

```bash
# Start a new piece of work
git checkout main
git pull origin main
git checkout -b your-branch-name

# Save your work
git add .
git commit -m "Short description of what you did"

# Upload to GitHub
git push origin your-branch-name

# Then go to GitHub and open a Pull Request
```

---

## Live Application Details

| Item | Value |
|------|-------|
| Live URL | https://lightstorm-itpmo.azurewebsites.net |
| GitHub Repo | https://github.com/kbasudevan/lightstorm-itpmo |
| Pipeline Status | https://github.com/kbasudevan/lightstorm-itpmo/actions |
| Hosting Platform | Microsoft Azure App Service (Southeast Asia) |
| Database | Azure PostgreSQL Flexible Server |
| Runtime | Python 3.11 + Flask + Gunicorn |

---

## Admin Access

The default admin account is `krishna.basudevan@lightstorm.net`. Change the password after first login.

Only users with a `@lightstorm.net`, `@lightstorm.in`, or `@lightstorm.sg` email address can register.
