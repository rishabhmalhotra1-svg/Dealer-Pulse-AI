#!/bin/bash
# DealerPulse AI — Power BI Credentials Setup
# Run this once to store your Azure credentials

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   DealerPulse AI — Power BI Credentials Setup           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
echo "Enter your Azure AD / Power BI credentials:"
echo "(These will be saved to .env file — never commit this file)"
echo ""

read -p "Tenant ID      : " TENANT_ID
read -p "Client ID      : " CLIENT_ID
read -s -p "Client Secret  : " CLIENT_SECRET
echo ""

cat > /home/user/Dealer-Pulse-AI/.env << ENVEOF
PBI_TENANT_ID=${TENANT_ID}
PBI_CLIENT_ID=${CLIENT_ID}
PBI_CLIENT_SECRET=${CLIENT_SECRET}
ENVEOF

echo ""
echo "✅ Saved to .env"
echo ""
echo "To use:"
echo "  source /home/user/Dealer-Pulse-AI/.env && python3 powerbi_connector.py --discover"
echo "  source /home/user/Dealer-Pulse-AI/.env && python3 powerbi_connector.py"
