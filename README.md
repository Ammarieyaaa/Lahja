# Lahja

Regression testing for LLM features, with first-class support for French, Arabic and Moroccan Darija.

*(Work in progress. The architecture and "hard problem" sections arrive with the final increment.)*

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env   # then add GROQ_API_KEY
pytest
lahja config
```
