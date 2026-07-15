import os
import subprocess
import json
from datetime import datetime

import stripe
from flask import Flask, request, jsonify
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

app = Flask(__name__)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")

PRINTER_NAME = "Ricoh_MP4000"
LOGO_PATH = "/var/www/fermiglow/assets/images/logo.png"


def money(amount_cents, currency):
    if amount_cents is None:
        return ""
    return f"${amount_cents / 100:.2f} {currency.upper()}"


def safe(value):
    if value is None:
        return ""
    return str(value)


def make_packing_slip(session, line_items):
    order_id = session.get("id", "")
    customer = session.get("customer_details") or {}
    shipping = session.get("shipping_details") or {}
    address = shipping.get("address") or customer.get("address") or {}

    name = shipping.get("name") or customer.get("name") or ""
    email = customer.get("email") or ""
    phone = customer.get("phone") or ""

    output = f"/tmp/fermiglow-order-{order_id}.pdf"

    c = canvas.Canvas(output, pagesize=A4)
    width, height = A4

    # Logo only, good for B&W printer
    if os.path.exists(LOGO_PATH):
        c.drawImage(
            LOGO_PATH,
            15 * mm,
            height - 28 * mm,
            width=55 * mm,
            height=18 * mm,
            preserveAspectRatio=True,
            mask="auto",
        )

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 20)
    c.drawRightString(width - 15 * mm, height - 18 * mm, "PACKING SLIP")

    c.setStrokeColor(colors.black)
    c.setLineWidth(1)
    c.line(15 * mm, height - 34 * mm, width - 15 * mm, height - 34 * mm)

    y = height - 45 * mm

    c.setFont("Helvetica-Bold", 15)
    c.drawString(15 * mm, y, "Your Business Order")

    c.setFont("Helvetica", 10)
    c.drawRightString(
        width - 15 * mm,
        y,
        datetime.now().strftime("%d/%m/%Y %I:%M %p"),
    )


    # Product table
    y -= 14 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, "Product")
    c.drawString(112 * mm, y, "Qty")
    c.drawString(140 * mm, y, "Amount")

    y -= 3 * mm
    c.setLineWidth(0.5)
    c.line(15 * mm, y, width - 15 * mm, y)

    y -= 9 * mm
    c.setFont("Helvetica", 11)

    if not line_items:
        line_items = [
            {
                "description": "Your Business Order",
                "quantity": 1,
                "amount_total": session.get("amount_total", 0),
            }
        ]

    for item in line_items:
        description = safe(item.get("description"))
        quantity = safe(item.get("quantity"))
        amount = money(item.get("amount_total"), session.get("currency", "aud"))

        c.drawString(15 * mm, y, description[:48])
        c.drawString(112 * mm, y, quantity)
        c.drawString(140 * mm, y, amount)
        y -= 8 * mm

    y -= 5 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(
        width - 15 * mm,
        y,
        "Total: " + money(session.get("amount_total"), session.get("currency", "aud")),
    )

    # Customer section
    y -= 18 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(15 * mm, y, "Customer Details")

    y -= 9 * mm
    c.setFont("Helvetica", 11)
    c.drawString(15 * mm, y, "Name: " + safe(name))

    y -= 8 * mm
    c.drawString(15 * mm, y, "Email: " + safe(email))

    y -= 8 * mm
    c.drawString(15 * mm, y, "Phone: " + safe(phone))

    y -= 10 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(15 * mm, y, "Shipping Address:")

    y -= 8 * mm
    c.setFont("Helvetica", 11)

    address_lines = [
        address.get("line1"),
        address.get("line2"),
        " ".join(
            filter(
                None,
                [
                    address.get("city"),
                    address.get("state"),
                    address.get("postal_code"),
                ],
            )
        ),
        address.get("country"),
    ]

    for line in address_lines:
        if line:
            c.drawString(18 * mm, y, safe(line))
            y -= 7 * mm

    # Packing checklist
    y -= 10 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(15 * mm, y, "Packing Checklist")

    check_items = [
        "Correct heater model packed",
        "Instruction manual included",
        "Box checked and sealed",
        "Shipping label attached",
        "Order marked as packed",
    ]

    c.setFont("Helvetica", 12)

    for item in check_items:
        y -= 9 * mm
        c.rect(17 * mm, y - 2 * mm, 4 * mm, 4 * mm, stroke=1, fill=0)
        c.drawString(25 * mm, y - 1 * mm, item)

    # Notes box
    y -= 18 * mm
    c.setFont("Helvetica-Bold", 13)
    c.drawString(15 * mm, y, "Notes")

    y -= 8 * mm
    c.rect(15 * mm, y - 25 * mm, width - 30 * mm, 28 * mm, stroke=1, fill=0)

    # Footer
    c.line(15 * mm, 22 * mm, width - 15 * mm, 22 * mm)
    c.setFont("Helvetica", 9)
    c.drawCentredString(
        width / 2,
        14 * mm,
        "Your Business  |  Your business details  |  Thank you for your order",
    )

    c.save()
    return output


def print_pdf(pdf_path):
    subprocess.run(
        [
            "lp",
            "-d",
            PRINTER_NAME,
            "-o",
            "PageSize=A4",
            "-o",
            "media=A4",
            pdf_path,
        ],
        check=True,
    )

@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except Exception as e:
        print("Webhook signature failed:", str(e), flush=True)
        return jsonify({"error": "bad signature", "details": str(e)}), 400

    try:
        # Convert Stripe object to a normal Python dict
        if hasattr(event, "to_dict_recursive"):
            event = event.to_dict_recursive()
        else:
            event = json.loads(payload.decode("utf-8"))

        event_type = event.get("type", "")

        # Normal Stripe webhook format
        if event_type == "checkout.session.completed":
            session = event["data"]["object"]

        # New Stripe Event Destination snapshot format
        elif event.get("object", {}).get("object") == "checkout.session":
            session = event["object"]
            event_type = "checkout.session.completed"

        else:
            print("Ignored event:", event_type, flush=True)
            return jsonify({"received": True, "ignored": True}), 200

        if session.get("payment_status") != "paid":
            print("Checkout not paid yet, ignored:", session.get("id"), flush=True)
            return jsonify({"received": True, "not_paid": True}), 200

        try:
            line_items_response = stripe.checkout.Session.list_line_items(
                session["id"],
                limit=10,
            )

            if hasattr(line_items_response, "to_dict_recursive"):
                line_items_response = line_items_response.to_dict_recursive()

            line_items = line_items_response.get("data", [])

        except Exception as e:
            print("Could not fetch line items, using fallback item:", str(e), flush=True)
            line_items = [
                {
                    "description": "Your Business Order",
                    "quantity": 1,
                    "amount_total": session.get("amount_total", 0),
                }
            ]

        if not line_items:
            line_items = [
                {
                    "description": "Your Business Order",
                    "quantity": 1,
                    "amount_total": session.get("amount_total", 0),
                }
            ]

        pdf_path = make_packing_slip(session, line_items)
        print_pdf(pdf_path)

        print("Printed order:", session.get("id"), flush=True)
        return jsonify({"received": True, "printed": True}), 200

    except Exception as e:
        print("Print failed:", str(e), flush=True)
        return jsonify({"error": "print failed", "details": str(e)}), 500

@app.route("/", methods=["GET"])
def home():
    return "Your Business Stripe printer is running."


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=4242)
