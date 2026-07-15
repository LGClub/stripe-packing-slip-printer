cat > README.md <<'EOF'
# Stripe Packing Slip Printer

A simple Python Flask app that listens for Stripe Checkout webhooks, creates a packing slip PDF, and prints it automatically.

Built for small businesses that want a low-cost way to print packing slips from Stripe orders.

## What it does

- Receives Stripe `checkout.session.completed` webhooks
- Checks the Checkout Session is paid
- Creates an A4 packing slip PDF
- Sends the PDF to a local printer using CUPS / `lp`
- Prevents the same Stripe session from printing twice

## Requirements

- Ubuntu/Linux server
- Python 3
- CUPS printer setup
- Stripe account
- Stripe Checkout
- Nginx reverse proxy recommended

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
