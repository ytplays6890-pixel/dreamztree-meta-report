# Dreamztree Meta Leads Report Web App

## Run on Windows

1. Install Python 3.10 or newer.
2. Put `app.py` and `requirements.txt` in the same folder.
3. Open Command Prompt in that folder and run:

```cmd
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

4. Your browser should open automatically at `http://localhost:8501`.

## How to use

- Upload the Meta Ads Excel export (`.xlsx`).
- Review the campaign assignments. Existing campaigns use the built-in mapping; new campaigns are inferred only when enough information is available.
- Edit Staff, Course, or Branch directly in the table for new/ambiguous campaigns.
- Click **Generate report**.
- Download the WhatsApp-ready `.txt` report and the updated mapping CSV.
- For future runs, upload your saved mapping CSV in the sidebar so confirmed new campaigns are recognized.

## Excel columns

The app looks for columns containing Campaign, Results (excluding Initial Results), and Amount Spent/Spent. It falls back to the first three columns if names cannot be found.

## Currency

The default USD-to-KD factor is `0.308`, inherited from the existing script. Verify the correct factor for your Meta export currency before relying on costs.
