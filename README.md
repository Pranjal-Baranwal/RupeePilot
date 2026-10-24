<<<<<<< HEAD

# RupeePilot — AI Financial Planning Team

RupeePilot is a multi-agent financial planning assistant built with Python
and the Fetch.ai uAgents framework.

It helps users analyze expenses, forecast cash flow, plan bill payments,
evaluate savings goals, simulate unexpected expenses, and verify proposed
budget plans.

## Architecture

RupeePilot uses seven independent agents:

1. **Coordinator Agent** — Orchestrates requests and agent communication.
2. **Expense Agent** — Analyzes spending categories and flexible expenses.
3. **Cash-Flow Agent** — Projects balances and identifies potential shortfalls.
4. **Bills Agent** — Evaluates mandatory payments and due dates.
5. **Goal Agent** — Evaluates savings targets and contribution changes.
6. **Scenario Agent** — Generates and ranks alternative budget plans.
7. **Verification Agent** — Independently checks calculations and assumptions.

## Technology Stack

- Python 3.11
- Fetch.ai uAgents
- ASI:One API for language understanding and explanations
- python-dotenv for environment configuration
- pytest for automated testing

## Project Status

Development is in progress.

The financial calculation engine will be implemented and tested before
the complete multi-agent workflow and external integrations.

## Setup

### 1. Create and activate a virtual environment

On Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and configure the required values when needed.

Keep API keys and agent seeds private. Never commit `.env` to GitHub.

### 4. Run tests

```powershell
python -m pytest
```

Tests will become available as the project modules are implemented.

### 5. Start the application

Once the agent network and entry point are implemented:

```powershell
python run.py
```

## Design Principles

- Use deterministic arithmetic for financial calculations.
- Validate user-provided data before generating a plan.
- Do not invent missing financial information.
- Independently verify candidate plans before presenting them.
- Clearly disclose assumptions, limitations, and infeasible scenarios.
- Do not execute payments or financial transactions.

## Security

Use synthetic financial data during development and demonstrations.
Never store bank passwords, publish API keys, or expose private agent seeds.

## License

To be determined.
=======

# RupeePilot — AI Financial Planning Team

RupeePilot is a multi-agent financial planning assistant built with Python
and the Fetch.ai uAgents framework.

It helps users analyze expenses, forecast cash flow, plan bill payments,
evaluate savings goals, simulate unexpected expenses, and verify proposed
budget plans.

## Architecture

RupeePilot uses seven independent agents:

1. **Coordinator Agent** — Orchestrates requests and agent communication.
2. **Expense Agent** — Analyzes spending categories and flexible expenses.
3. **Cash-Flow Agent** — Projects balances and identifies potential shortfalls.
4. **Bills Agent** — Evaluates mandatory payments and due dates.
5. **Goal Agent** — Evaluates savings targets and contribution changes.
6. **Scenario Agent** — Generates and ranks alternative budget plans.
7. **Verification Agent** — Independently checks calculations and assumptions.

## Technology Stack

- Python 3.11
- Fetch.ai uAgents
- ASI:One API for language understanding and explanations
- python-dotenv for environment configuration
- pytest for automated testing

## Project Status

Development is in progress.

The financial calculation engine will be implemented and tested before
the complete multi-agent workflow and external integrations.

## Setup

### 1. Create and activate a virtual environment

On Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and configure the required values when needed.

Keep API keys and agent seeds private. Never commit `.env` to GitHub.

### 4. Run tests

```powershell
python -m pytest
```

Tests will become available as the project modules are implemented.

### 5. Start the application

Once the agent network and entry point are implemented:

```powershell
python run.py
```

## Design Principles

- Use deterministic arithmetic for financial calculations.
- Validate user-provided data before generating a plan.
- Do not invent missing financial information.
- Independently verify candidate plans before presenting them.
- Clearly disclose assumptions, limitations, and infeasible scenarios.
- Do not execute payments or financial transactions.

## Security

Use synthetic financial data during development and demonstrations.
Never store bank passwords, publish API keys, or expose private agent seeds.

## License

To be determined.
>>>>>>> dd5d9c1de235f600e530c8250762d54b89e10935
