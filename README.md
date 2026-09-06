# Sicsicduck 🦆

A real-time US Treasury yield curve visualization tool with historical data tracking.

## Live Demo

🌐 **[sicsicduck.com/treasury-yields](https://sicsicduck.com/treasury-yields.html)**

## Features

- 📈 **Interactive yield curve chart** with historical data (30 days)
- 🔄 **Real-time updates** via Yahoo Finance API
- 📊 **Multiple maturities**: 3M, 2Y, 5Y, 10Y, 30Y
- 📱 **Responsive design** for desktop and mobile
- 🔍 **Key spread indicators**: 10Y-2Y and 10Y-3M

## Current Yields

| Maturity | Yield | Date |
|----------|-------|------|
| 3M | 3.757% | 2026-09-06 |
| 2Y | 3.961% | 2026-09-06 |
| 5Y | 4.55% | 2026-09-06 |
| 10Y | 4.784% | 2026-09-06 |
| 30Y | 5.246% | 2026-09-06 |


### Key Spreads

- **10Y-2Y Spread**: 0.823% (normal)
- **10Y-3M Spread**: 1.027% (normal)

*Last updated: 2026-09-06T17:00:07.183184 (Asia/Hong_Kong)*

## What it Does

Sicsicduck tracks US Treasury yields across different maturities to visualize the yield curve shape. The yield curve is a key economic indicator:

- **Normal curve** (upward sloping): Healthy economy expectations
- **Inverted curve** (downward sloping): Recession signal
- **Flat curve**: Uncertainty about future rates

## Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Charting**: [Chart.js](https://www.chartjs.org/)
- **Data Source**: Yahoo Finance API
- **Deployment**: GitHub Pages + OpenClaw automation
- **Language**: 中文介面 (Chinese UI)

## Architecture

```
sicsicduck/
├── treasury-yields.html      # Main yield curve viewer
├── treasury-yields.png       # Chart image for embedding
├── data/
│   └── treasury_yields.json  # Historical yield data (30 days)
├── scripts/
│   └── update_treasury_yields.py  # Data update automation
├── index.html                # Landing page
└── README.md                 # This file
```

## How It Works

1. **Data Collection**: Python script fetches yields from Yahoo Finance
2. **Data Storage**: JSON file maintains 30-day rolling window
3. **Visualization**: Chart.js renders interactive line chart
4. **Automation**: Cron job updates data every hour
5. **Deployment**: GitHub Pages hosts the static site

## Development

### Prerequisites

- Python 3.8+
- `yfinance` library
- Modern web browser

### Local Development

```bash
# Clone the repository
git clone https://github.com/freetadi-cell/sicsicduck.git
cd sicsicduck

# Install Python dependencies
pip install yfinance

# Update yield data
python3 scripts/update_treasury_yields.py

# Open in browser
open treasury-yields.html
```

### Updating Data

```bash
python3 scripts/update_treasury_yields.py
```

This script:
- Fetches latest yields from Yahoo Finance
- Appends to historical data (keeps 30 days)
- Updates the HTML with embedded chart data
- Commits and pushes changes to GitHub

## Data Sources

| Maturity | Yahoo Finance Symbol |
|----------|---------------------|
| 3-Month | ^IRX |
| 2-Year | 2YY=F |
| 5-Year | ^FVX |
| 10-Year | ^TNX |
| 30-Year | ^TYX |

## License

This project is open source. See repository for license details.

---

*Built with 💛 by [OpenClaw](https://openclaw.dev)*
