#!/usr/bin/env python3
"""
TPC Louisiana – Gator Drip Center Shafted Mallet stock checker.
Checks the product page daily and sends a Gmail alert.

Required environment variables (set as GitHub Actions secrets):
  ANTHROPIC_API_KEY   – your Anthropic API key
  GMAIL_ADDRESS       – your Gmail address (sender & recipient)
  GMAIL_APP_PASSWORD  – Gmail App Password (NOT your regular password)
"""

import os
import json
import smtplib
import re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import anthropic

PRODUCT_URL = (
    "https://tpc-louisiana.square.site/product/gator-drip-silver-navy-covers/"
    "7GRJRGO3K3Q4FUVVGOBIDVW4?cp=true&sa=false&sbp=false&q=false"
    "&category_id=VHBFAZRPTCAGL2KOKKF22HEY"
)
TARGET_VARIANT = "Center Shafted Mallet"
PRODUCT_NAME = "Gator Drip Silver & Navy Covers"
PRICE = "$119.00"


def check_stock() -> dict:
    """Ask Claude to fetch the product page and check stock status."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""You are a stock-checking agent. Use the web search tool to fetch this exact URL 
and determine the stock status of every variant in the dropdown, especially "{TARGET_VARIANT}":

{PRODUCT_URL}

Look at the dropdown options on the page. Each variant will either be available or show "Out of stock".

Return ONLY a valid JSON object — no markdown, no explanation, nothing else:
{{
  "targetVariant": "{TARGET_VARIANT}",
  "inStock": true_or_false,
  "allVariants": [
    {{"name": "variant name", "inStock": true_or_false}}
  ],
  "checkedAt": "ISO 8601 timestamp"
}}"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text content from response
    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    # Parse JSON from response
    json_match = re.search(r"\{[\s\S]*\}", raw_text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback if parsing fails
    return {
        "targetVariant": TARGET_VARIANT,
        "inStock": False,
        "allVariants": [],
        "checkedAt": datetime.utcnow().isoformat(),
        "parseError": True,
        "rawResponse": raw_text[:500],
    }


def send_email(stock_data: dict) -> None:
    """Send a stock status email via Gmail SMTP."""
    gmail_address = os.environ["GMAIL_ADDRESS"]
    gmail_app_password = os.environ["GMAIL_APP_PASSWORD"]

    in_stock = stock_data.get("inStock", False)
    checked_at = stock_data.get("checkedAt", datetime.utcnow().isoformat())

    # Format checked time nicely
    try:
        dt = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        checked_str = dt.strftime("%B %d, %Y at %I:%M %p UTC")
    except Exception:
        checked_str = checked_at

    # Build subject
    if in_stock:
        subject = f"🎉 {TARGET_VARIANT} is BACK IN STOCK – TPC Louisiana"
    else:
        subject = f"📋 Daily update: {TARGET_VARIANT} still out of stock – TPC Louisiana"

    # Build variant table
    variants = stock_data.get("allVariants", [])
    if variants:
        variant_lines = "\n".join(
            f"  {'✅' if v['inStock'] else '❌'} {v['name']}: {'In stock' if v['inStock'] else 'Out of stock'}"
            for v in variants
        )
    else:
        status_word = "In stock ✅" if in_stock else "Out of stock ❌"
        variant_lines = f"  {TARGET_VARIANT}: {status_word}"

    # Build body
    if in_stock:
        call_to_action = (
            "🚨 IT'S BACK! Don't wait — head to the link below and buy it now "
            "before it sells out again.\n"
        )
    else:
        call_to_action = "Still out of stock. Will check again tomorrow.\n"

    body = f"""TPC Louisiana – {PRODUCT_NAME}
Daily Stock Alert
{'=' * 50}

TARGET: {TARGET_VARIANT}
STATUS: {'✅ IN STOCK' if in_stock else '❌ Out of stock'}

{call_to_action}
All variants:
{variant_lines}

Product page:
{PRODUCT_URL}

Price: {PRICE}
Checked: {checked_str}

{'=' * 50}
This is your automated daily stock alert.
To stop receiving these, disable the GitHub Actions workflow.
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_address
    msg["To"] = gmail_address
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_address, gmail_app_password)
        server.sendmail(gmail_address, gmail_address, msg.as_string())

    print(f"Email sent: {subject}")


def main():
    print(f"[{datetime.utcnow().isoformat()}] Checking stock for {TARGET_VARIANT}...")

    stock_data = check_stock()
    in_stock = stock_data.get("inStock", False)
    variants = stock_data.get("allVariants", [])

    print(f"Target variant ({TARGET_VARIANT}): {'IN STOCK' if in_stock else 'out of stock'}")
    if variants:
        for v in variants:
            print(f"  {v['name']}: {'in stock' if v['inStock'] else 'out of stock'}")

    if stock_data.get("parseError"):
        print(f"Warning: could not parse structured response. Raw: {stock_data.get('rawResponse', '')}")

    send_email(stock_data)
    print("Done.")


if __name__ == "__main__":
    main()
 
