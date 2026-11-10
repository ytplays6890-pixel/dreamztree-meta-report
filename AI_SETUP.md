# AI Marketing Intelligence setup

The AI features are optional. Rule-based campaign alerts, branch summaries, cost-per-lead comparisons, and run-rate estimates work without an AI API key.

## Enable Google Gemini (recommended)

1. Create or copy your Gemini API key from [Google AI Studio](https://aistudio.google.com/).
2. Open your deployed Streamlit app's app settings and find **Secrets**.
3. Add these values at the top level of the TOML file, outside any section such as [supabase]:

```toml
GEMINI_API_KEY = "your-gemini-api-key"
GEMINI_MODEL = "gemini-2.5-flash"
```

4. Save the secrets and allow the app to restart/redeploy.

The app prefers Gemini whenever GEMINI_API_KEY is configured. If Gemini is not configured, it can still use the existing OPENAI_API_KEY / OPENAI_MODEL settings as a fallback.

For local development, place the same values in `.streamlit/secrets.toml`. Do not commit that file to GitHub. Never paste API keys into chat or screenshots.

## Included capabilities

- Rule-based alerts for unassigned campaigns and unusually high cost per lead.
- Branch performance comparisons using attributed campaign data.
- Relative budget recommendations; the app never changes Meta campaign budgets.
- Lead run-rate estimates using today's upload and optional historical daily exports.
- Gemini-generated campaign analysis and management summary.
- Chat with the currently uploaded report.

## Data and forecast limitations

- Gemini answers use the campaign metrics supplied in the current report session. Do not upload personal or sensitive lead-level information.
- The app's calculations remain local Python calculations; the AI service is used to interpret aggregate campaign metrics.
- Gemini API free-tier availability, model access, rate limits, and data-use terms are controlled by Google and may change. Check the terms for your account and region.
- Upload one previous-day file and/or multiple historical daily exports to improve trend context.
- The forecast is an arithmetic average/run-rate estimate, not a trained machine-learning model or a guarantee.
- A weekly summary is only meaningful when at least seven daily exports are supplied. Otherwise the AI should describe the actual uploaded reporting period.
- Budget recommendations are decision support only. Check lead quality, conversion rate, and business context before making changes.
