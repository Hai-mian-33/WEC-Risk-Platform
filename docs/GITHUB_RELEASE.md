# Publishing the camera-ready update to GitHub

Run the commands from the root of your local clone. Its configured remote is:

```text
https://github.com/Hai-mian-33/WEC-Risk-Platform.git
```

Use a review branch rather than pushing directly to `main`.

## 1. Verify the local revision

Run in PowerShell:

```powershell
Set-Location '<path-to-your-local-WEC_Platform_Release-clone>'
git status
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python paper_revision\verify_release.py
git diff --check
```

Inspect the diff and confirm that no restricted raw data, credentials, build
directories, or machine-local paths have been staged.

## 2. Commit intentionally

```powershell
git switch agent/wrem-final-layout-data-docs
git add README.md README_English.md README_中文.md DATA_PROVENANCE.md
git add wec_platform examples tests docs paper_revision data\Miyun\factor_screening_frame_final.csv
git status --short
git diff --cached --stat
git commit -m "fix: align public workflow with camera-ready analysis"
```

## 3. Push the branch

```powershell
git push -u origin agent/wrem-final-layout-data-docs
```

If GitHub authentication is requested, sign in with the account that has
write access to `Hai-mian-33/WEC-Risk-Platform` or use a scoped personal access
token. Do not paste a token into a tracked file.

## 4. Open a pull request

With GitHub CLI:

```powershell
gh pr create --repo Hai-mian-33/WEC-Risk-Platform `
  --base main `
  --head agent/wrem-final-layout-data-docs `
  --title "Align WEC-Risk with the WR26-014 camera-ready analysis" `
  --body-file docs\PR_BODY_WREM_FINAL.md
```

Alternatively, open the repository page after pushing and use **Compare & pull
request**. Review the data-provenance, license/patent, and test sections before
merging.

## 5. Optional source release after merge

Create a tagged GitHub Release only after the pull request is reviewed and
merged. Do not attach a PyQt5-bundled executable without separately checking
the binary redistribution obligations described in `NOTICE`.
