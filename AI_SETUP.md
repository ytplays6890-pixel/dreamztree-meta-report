# AI Marketing Intelligence setup

The AI features are optional. Rule-based campaign alerts, branch summaries, cost-per-lead comparisons, and run-rate estimates work without an AI API key.

## Enable OpenAI analysis and report chat

1. Create an OpenAI API key in your OpenAI developer account.
2. Open your deployed Streamlit app's app settings and find **Secrets**.
3. Add the following values (replace the example with your own key):

```toml
OPENAI_API_KEY = "your-private-api-key"
OPENAI_MODEL = "gpt-4o-mini"
```

4. Save the secrets and restart/redeploy the Streamlit app.

For local development, place the same values in `.streamlit/secrets.toml`. Do not commit that file to GitHub.

## Included capabilities

- Rule-based alerts for unassigned campaigns and unusually high cost per lead.
- Branch performance comparisons using attributed campaign data.
- Relative budget recommendations; the app never changes Meta campaign budgets.
- Lead run-rate estimates using today's upload and optional historical daily exports.
- OpenAI-generated campaign analysis and management summary.
- Chat with the currently uploaded report.

## Data and forecast limitations

- AI answers use the campaign metrics supplied in the current report session. Do not upload personal or sensitive lead-level information.
- The app's calculations remain local Python calculations; the AI service is used to interpret aggregate campaign metrics.
- Upload one previous-day file and/or multiple historical daily exports to improve trend context.
- The forecast is an arithmetic average/run-rate estimate, not a trained machine-learning model or a guarantee.
- A weekly summary is only meaningful when at least seven daily exports are supplied. Otherwise the AI should describe the actual uploaded reporting period.
- Budget recommendations are decision support only. Check lead quality, conversion rate, and business context before making changes.
