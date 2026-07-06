# [.tikzon] — Resale Arbitrage Research Agent

`.tikzon` is a daily-running product arbitrage research system. It scans trending TikTok Shop products in the US, sources suppliers from AliExpress, Alibaba, and 1688, verifies profitability and competition on Amazon, and sends a daily morning email digest to the operator.

All final purchase and listing decisions are **human-in-the-loop**. The agent does not place orders or make financial transactions autonomously.

---

## 📂 Folder Structure

```
.tikzon/
├── .env.example             # Template for local environment variables
├── README.md                # This setup and operating guide
├── requirements.txt         # Python dependencies
│
├── config/
│   ├── skills.json          # Registry for agent skills
│   └── scan_config.json     # Configuration file for categories, thresholds, and filters
│
├── memory/
│   ├── context.json         # Session metadata and statistics
│   └── product_log.json     # Local cache tracking products and statuses
│
├── skills/                  # SKILL.md behavioral modules for the agent
│   ├── arbitrage_pipeline.md
│   ├── tiktok_discovery.md
│   ├── supplier_sourcing.md
│   ├── amazon_checker.md
│   ├── profit_calculator.md
│   └── report_builder.md
│
├── scripts/                 # Core logic implementation (Python)
│   ├── main.py              # Orchestration entry point
│   ├── config.py            # Settings loader & validator
│   ├── models.py            # Pydantic schema declarations
│   ├── tiktok_scraper.py    # TikTok scraper & qualifiers
│   ├── supplier_search.py   # AliExpress, Alibaba & 1688 search
│   ├── amazon_checker.py    # Gating and competition checker
│   ├── profit_calc.py       # landed costs & margin validator
│   ├── sheets_manager.py    # Google Sheets read/write controller
│   ├── email_sender.py      # Email digest renderer & sender
│   └── utils.py             # Loggers & decorators
│
├── templates/
│   └── email_digest.html    # Jinja2 template for email reports
│
└── n8n/
    └── workflow.json        # Preconfigured daily n8n scheduling workflow
```

---

## 🚀 Setup Instructions

### 1. Installation & Environment
1. Clone or download this folder to your local machine (e.g. `C:\Users\Jon\Desktop\.tikzon`).
2. Open a terminal, navigate to the directory, and install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Copy `.env.example` to `.env` in the root folder:
   ```bash
   copy .env.example .env
   ```

### 2. Email Setup (Gmail SMTP)
To receive morning digests, configure a Gmail sender:
1. Ensure your Gmail account has **2-Step Verification** enabled.
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords).
3. Generate a new App Password (select "Other (custom name)", e.g., `tikzon`).
4. Copy the generated 16-character code and paste it in `.env`:
   - `SMTP_USER=your_gmail@gmail.com`
   - `SMTP_PASSWORD=your_16_char_app_password`
   - `OPERATOR_EMAIL=your_personal_email@gmail.com`

---

## 📊 Google Sheets Setup

The agent logs opportunities in a Google Sheet containing two tabs: `Opportunities` and `Scan Log`.

### Step 1: Create a Google Cloud Project & Service Account
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. `tikzon-arbitrage`).
3. Search for the **Google Sheets API** and click **Enable**.
4. Search for the **Google Drive API** and click **Enable**.
5. Go to **APIs & Services** → **Credentials**.
6. Click **Create Credentials** and select **Service Account**.
7. Provide a name, click **Create and Continue**, then click **Done**.

### Step 2: Download Credentials JSON
1. Click on your newly created Service Account email.
2. Navigate to the **Keys** tab.
3. Click **Add Key** → **Create New Key**.
4. Select **JSON** and click **Create**.
5. Save the downloaded JSON file as `service_account.json` inside the `config/` directory (so its path matches `.tikzon/config/service_account.json`).

### Step 3: Link the Google Sheet
1. Create a new Google Sheet in your web browser.
2. Click **Share** (top-right) and add the Service Account's email address (copied from the Credentials console) as an **Editor**. Uncheck "Notify people".
3. Copy the Google Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/`**`[YOUR_GOOGLE_SHEET_ID]`**`/edit`
4. Paste the ID in `.env`:
   - `GOOGLE_SHEET_ID=your_google_sheet_id_here`

---

## ⏰ Schedule Setup

You can schedule the agent to run daily at 5:00 AM using Windows Task Scheduler or n8n.

### Option A: Windows Task Scheduler (Recommended)
1. Open the Start menu, search for **Task Scheduler**, and open it.
2. Click **Create Basic Task** in the Actions panel.
3. Name it `tikzon_arbitrage` and set the Trigger to **Daily**.
4. Set the Start Time to `5:00:00 AM`.
5. Select **Start a Program** as the Action.
6. Configure the program parameters:
   - **Program/script**: `python` (or the path to your Python executable, e.g. `C:\Users\Jon\AppData\Local\Programs\Python\Python311\python.exe`)
   - **Add arguments**: `scripts/main.py`
   - **Start in**: `C:\Users\Jon\Desktop\.tikzon` (or the absolute path to your `.tikzon` directory)
7. Click **Finish**.

### Option B: n8n Workflow
1. Install and start n8n.
2. Click **Add Workflow** → **Import from File**.
3. Import `n8n/workflow.json`.
4. Ensure the **Execute Command** node references your correct python environment and directory path.
5. Activate the workflow.

---

## 🛠️ Operating Commands

### Validate Setup (Dry Run)
Verify imports, environment variables, and Sheet permissions without scraping:
```bash
python scripts/main.py --dry-run
```

### Manual Scan Run (Immediate)
Run a full scan immediately (overrides scheduling lock):
```bash
python scripts/main.py --force
```

### Scan Specific Categories
Run a scan targeting specific categories:
```bash
python scripts/main.py --categories beauty,home
```

### Approve a Product
When you receive the morning digest and want to approve an opportunity, run:
```bash
python scripts/main.py --approve "Product Name"
```
*This updates Google Sheets to `approved`, updates local memory logs, prints supplier contact details and ordering steps directly to the console, and emails them to you for manual purchase execution.*

---

## 📚 How to Add a New Skill

To extend the agent's capabilities with a new skill:
1. **Define the Skill**: Create a Markdown file in `skills/` (e.g. `skills/brand_kit.md`) with YAML frontmatter:
   ```markdown
   ---
   name: brand_kit
   description: Guidelines on brand kit design and marketing assets.
   ---
   # Brand Kit Instructions
   (Write the system instructions for this skill here...)
   ```
2. **Register the Skill**: Add a corresponding entry in `config/skills.json` under `skills`:
   ```json
   {
     "name": "brand_kit",
     "description": "Guidelines on brand kit design and marketing assets.",
     "trigger_phrases": [
       "create a brand kit",
       "update logo and colors",
       "generate marketing assets"
     ],
     "file": "skills/brand_kit.md"
   }
   ```
3. **Execute the Skill**: Load the contents of the skill markdown file into Antigravity's context when triggered by any of the registered phrases.
