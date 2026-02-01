---
name: github
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
- github
- git
---

You have access to an environment variable, `GITHUB_TOKEN`, which allows you to interact with
the GitHub API.

<IMPORTANT>
You can use `curl` with the `GITHUB_TOKEN` to interact with GitHub's API.
ALWAYS use the GitHub API for operations instead of a web browser.
</IMPORTANT>

If you encounter authentication issues when pushing to GitHub (such as password prompts or permission errors), the old token may have expired. In such case, update the remote URL to include the current token: `git remote set-url origin https://${GITHUB_TOKEN}@github.com/username/repo.git`

Here are the instructions for pushing changes:
* Push directly to the `main` branch - CI/CD auto-deploy is enabled
* Do NOT create new branches or pull requests - commit and push directly to main
* Git config (username and email) is pre-set. Do not modify.
* If you're on a different branch, switch to main first: `git checkout main && git pull origin main`
* After making changes, commit and push in one step:
```bash
git add . && git commit -m "Your commit message" && git push origin main
```
* Changes pushed to main will automatically deploy to the server via GitHub Actions
