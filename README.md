# Fully Automatic News → Stock Scanner

This version runs automatically with GitHub Actions and publishes the latest report to GitHub Pages.

## Automatic schedule

- Monday-Friday 10:00 Doha/Türkiye time
- Monday-Friday 17:00 Doha/Türkiye time

GitHub Actions cron uses UTC:
- 10:00 Doha/Türkiye = 07:00 UTC
- 17:00 Doha/Türkiye = 14:00 UTC

## Files

- `news_stock_scanner_v2.py` = main scanner
- `requirements.txt` = Python packages
- `.github/workflows/auto_scanner.yml` = automatic schedule
- `docs/index.html` = latest HTML report published by GitHub Pages
- `docs/latest.csv` = latest CSV report after the first run

## One-time setup

1. Create a GitHub repository named `news-stock-scanner`.
2. Upload all files/folders from this package.
3. Go to repository Settings → Pages.
4. Choose:
   - Source: Deploy from a branch
   - Branch: main
   - Folder: /docs
5. Save.
6. After the scheduled run, open:
   `https://YOUR_GITHUB_USERNAME.github.io/news-stock-scanner/`

No manual run is required after setup.
