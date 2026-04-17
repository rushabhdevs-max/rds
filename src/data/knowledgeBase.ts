import type { KnowledgeBase } from "@/lib/types";

export const knowledgeBase: KnowledgeBase = {
  onboarding: {
    domainName: "Onboarding",
    description: "Merchant registration, KYC, device activation, and account setup for Airpay PoS.",
    entries: [
      {
        topic: "Merchant Registration",
        description: "How a new merchant signs up for Airpay PoS services.",
        steps: [
          "Visit airpay.co.in or the Airpay Merchant app and tap 'Register'.",
          "Enter business name, contact number, email, and business category (retail, F&B, services, etc.).",
          "Upload required KYC documents (PAN, GST, Aadhaar, cancelled cheque/bank statement).",
          "Provide business address with proof (electricity bill, rent agreement, or shop license).",
          "Select the PoS device model (Airpay Mini, Airpay Smart, or Airpay Android PoS).",
          "Sign the merchant agreement digitally and complete eKYC via OTP.",
          "Submit — you will receive a Merchant ID (MID) within 24-48 hours after verification.",
        ],
        notes: [
          "Activation typically takes 2-3 business days after successful KYC.",
          "You must have a current account in a supported bank for settlements.",
        ],
      },
      {
        topic: "KYC Verification",
        description: "Documents required and the verification process.",
        steps: [
          "Individual merchants: PAN + Aadhaar (e-sign), bank proof, photograph.",
          "Proprietorship: PAN of proprietor, GST certificate (if applicable), shop license.",
          "Partnership/LLP/Pvt Ltd: Company PAN, Certificate of Incorporation, MOA/AOA, board resolution, authorized signatory KYC.",
          "Documents verified by Airpay compliance team within 24 hours on business days.",
        ],
        commonIssues: [
          "Blurry document images — re-upload with clear, well-lit scans.",
          "Name mismatch between PAN and bank account — submit a name-change affidavit or update bank records.",
          "GST certificate expired — renew before resubmitting.",
        ],
      },
      {
        topic: "Device Activation",
        description: "Activate a newly received Airpay PoS device.",
        steps: [
          "Unbox the device and charge it fully before first use.",
          "Power on — the device boots to the Airpay activation screen.",
          "Insert the provided SIM or connect to Wi-Fi.",
          "Enter the 10-digit Merchant ID (MID) printed on your welcome letter.",
          "Enter the activation OTP sent to your registered mobile number.",
          "The device downloads the latest configuration and transaction keys.",
          "Once you see 'Ready to Transact', perform a test transaction of Re. 1 to confirm.",
        ],
        commonIssues: [
          "'Invalid MID' — confirm you entered the correct Merchant ID; it is case-sensitive.",
          "'Activation failed - server unreachable' — check network connectivity and retry.",
          "OTP not received — ensure mobile is reachable; tap 'Resend OTP' after 60 seconds.",
        ],
      },
      {
        topic: "Account Setup",
        description: "Configure bank details, settlement preferences, and user access.",
        steps: [
          "Log in to the Airpay Merchant Portal with your MID and password.",
          "Go to Settings > Bank Details and add your current account (IFSC, account number, account name).",
          "Set settlement frequency: T+1 (default), Instant Settlement (requires activation), or custom.",
          "Create sub-users (cashier, manager) under Settings > User Management with role-based access.",
          "Enable SMS/email receipt notifications under Settings > Notifications.",
        ],
      },
    ],
  },
  merchantSolutions: {
    domainName: "Merchant Solutions",
    description: "Payment acceptance, QR codes, settlements, and reporting.",
    entries: [
      {
        topic: "Payment Methods Supported",
        description: "Payment instruments accepted by Airpay PoS.",
        notes: [
          "Cards: Visa, Mastercard, RuPay, Amex, Diners — contactless (tap), chip insert, or magstripe swipe.",
          "UPI: QR scan, UPI ID entry, and UPI Intent flows (GPay, PhonePe, Paytm, BHIM).",
          "Wallets: Paytm, Mobikwik, Amazon Pay, PhonePe wallet.",
          "EMI: Brand EMI, No-Cost EMI, Cardless EMI (select banks).",
          "Buy Now Pay Later (BNPL): LazyPay, Simpl (subject to activation).",
        ],
      },
      {
        topic: "Dynamic QR Codes",
        description: "Generate a QR code for a specific transaction amount.",
        steps: [
          "On the device, select 'QR Pay' from the home screen.",
          "Enter the transaction amount.",
          "The device displays a dynamic UPI QR valid for 5 minutes.",
          "Customer scans with any UPI app — payment is confirmed in real time.",
          "Device prints/emails a receipt once the webhook confirms success.",
        ],
      },
      {
        topic: "Settlement Cycles",
        description: "When transaction amounts are credited to your bank.",
        notes: [
          "T+1 (default): Funds credited the next working day by 11:00 AM.",
          "Instant Settlement: Credit within 30 minutes of the transaction (fee applies, activation required).",
          "Sundays and bank holidays are not considered business days for T+1 settlements.",
          "Settlement includes transaction value minus MDR (Merchant Discount Rate) and applicable GST.",
        ],
      },
      {
        topic: "Reports and Dashboard",
        description: "View and export transaction data.",
        steps: [
          "Log in to merchant.airpay.co.in.",
          "Navigate to Reports > Transactions for a real-time list.",
          "Use filters for date range, payment method, status, or terminal ID.",
          "Export as CSV, Excel, or PDF for accounting.",
          "Schedule automatic daily/weekly email reports under Reports > Automation.",
        ],
      },
    ],
  },
  integrations: {
    domainName: "Integrations",
    description: "APIs, SDKs, plugins, and sandbox support.",
    entries: [
      {
        topic: "REST API Overview",
        description: "Integrate Airpay payments into your website, app, or ERP.",
        notes: [
          "Base URL (prod): https://payments.airpay.co.in/pay/index.php",
          "Base URL (sandbox): https://kraken.airpay.co.in/pay/index.php",
          "Authentication: HMAC-SHA256 signature using your merchant secret key.",
          "Key endpoints: /order/create, /order/status, /order/refund, /settlement/report.",
          "Webhooks: Configure a callback URL in Merchant Portal > Settings > Webhooks to receive real-time events.",
        ],
      },
      {
        topic: "SDKs",
        description: "Official SDKs to embed Airpay checkout.",
        notes: [
          "Android SDK: available on Maven Central as `co.in.airpay:checkout-sdk`.",
          "iOS SDK: distributed via CocoaPods — `pod 'AirpayCheckout'`.",
          "Web JS SDK: <script src='https://payments.airpay.co.in/sdk/v2/checkout.js'></script>.",
          "Flutter & React Native bridges available on the Airpay GitHub org.",
        ],
      },
      {
        topic: "Plugins",
        description: "Ready-made plugins for popular platforms.",
        notes: [
          "Shopify: Install the 'Airpay Payments' app from the Shopify App Store.",
          "WooCommerce: Download the plugin ZIP from merchant portal > Integrations.",
          "Magento, PrestaShop, OpenCart plugins are also available.",
          "Tally & Zoho Books integrations for automated reconciliation.",
        ],
      },
      {
        topic: "Sandbox and Testing",
        description: "Test your integration without real money.",
        steps: [
          "Request sandbox credentials at developers.airpay.co.in.",
          "Use test card 4111 1111 1111 1111 with any future expiry and CVV 123.",
          "Test UPI success: use VPA `success@airpay`; failure: `failure@airpay`.",
          "Verify webhook delivery with the Webhook Simulator in the developer console.",
          "Once flows pass, request production credentials via your account manager.",
        ],
      },
    ],
  },
  issues: {
    domainName: "Issues and Troubleshooting",
    description: "Device errors, connectivity, software updates, and hardware issues.",
    entries: [
      {
        topic: "Common Error Codes",
        description: "Standard Airpay PoS error codes and resolutions.",
        notes: [
          "E01 - Network unreachable: check SIM/Wi-Fi, restart device.",
          "E05 - Invalid terminal key: re-run activation; contact support if it persists.",
          "E12 - Card read error: clean the reader, retry insert/swipe.",
          "E21 - Transaction declined by issuer: advise customer to use another card.",
          "E30 - Battery critical: charge the device before transacting.",
          "E45 - Printer jam/out of paper: replace paper roll (57mm thermal).",
          "E99 - Unknown error: note the reference ID on screen and contact support.",
        ],
      },
      {
        topic: "Connectivity Issues",
        description: "Device cannot connect to network.",
        steps: [
          "Check SIM signal strength (top-right icon) — should be 2 bars or more.",
          "Restart the device (long-press power > Restart).",
          "For Wi-Fi: Settings > Wi-Fi > reconnect to your network, verify password.",
          "If SIM: confirm data plan active, try removing/reinserting the SIM.",
          "Test with Airpay test utility: Menu > Diagnostics > Network Test.",
          "If still failing, swap to backup connection (Wi-Fi <-> SIM).",
        ],
      },
      {
        topic: "Software Updates",
        description: "Keep device firmware and Airpay app up to date.",
        steps: [
          "Updates are delivered OTA (over-the-air) automatically when device is idle and online.",
          "Manual check: Menu > Settings > Software Update > Check Now.",
          "Device must be on charger or above 40% battery to install updates.",
          "Do not power off during update; it takes 3-5 minutes.",
        ],
      },
      {
        topic: "Hardware Issues",
        description: "Physical problems with the PoS device.",
        commonIssues: [
          "Printer not printing — check paper orientation (thermal side facing reader), replace roll.",
          "Display flickering — perform a factory reset (Menu > Settings > Reset > keep MID).",
          "Card reader unresponsive — clean chip contacts with a cleaning card; clean mag-stripe slot.",
          "Battery drains quickly — replace battery (contact support for RMA if under warranty).",
          "Buttons unresponsive — hard reset by holding power + volume down for 10 seconds.",
        ],
        notes: [
          "Warranty: 1 year on device, 6 months on battery and accessories.",
          "For RMA, raise a ticket at merchant portal > Support > Device Issue.",
        ],
      },
    ],
  },
  cardResolutions: {
    domainName: "Card Resolutions",
    description: "Chargebacks, refunds, declined transactions, and card reader care.",
    entries: [
      {
        topic: "Refund Process",
        description: "Refund a successful card transaction to the customer.",
        steps: [
          "On the device: Menu > Transactions > find the transaction.",
          "Select 'Refund' and enter full or partial amount.",
          "Authorize with the merchant PIN.",
          "Customer receives refund to original card within 5-7 working days.",
          "You can also refund via Merchant Portal > Transactions > Refund action.",
        ],
        notes: [
          "Same-day full refunds are treated as Void and reverse instantly.",
          "Refunds after settlement are debited from your next settlement.",
        ],
      },
      {
        topic: "Chargebacks",
        description: "Customer disputes a transaction with their bank.",
        steps: [
          "You receive a chargeback notification via email and portal alert.",
          "Go to Merchant Portal > Disputes > open case.",
          "Submit evidence within 7 days: invoice, delivery proof, customer communication, CCTV if applicable.",
          "Airpay forwards evidence to the acquiring bank; verdict in 30-45 days.",
          "If ruled in merchant favour, amount is re-credited. If not, debited from settlements.",
        ],
        notes: [
          "Common reasons: 'service not received', 'unrecognized charge', 'duplicate charge'.",
          "Maintain transaction records for at least 180 days to defend disputes.",
        ],
      },
      {
        topic: "Declined Transactions",
        description: "Why a card payment fails.",
        notes: [
          "Insufficient funds — advise customer to use another card or payment method.",
          "Expired card — check expiry printed on card.",
          "Card blocked — customer should contact card-issuing bank.",
          "PIN incorrect — customer can retry, or use contactless.",
          "EMV read failure — retry insert, or fall back to swipe if permitted.",
          "AVS/CVV mismatch — verify customer entered correct details on CNP transactions.",
        ],
      },
      {
        topic: "Card Reader Maintenance",
        description: "Keep the card reader clean and reliable.",
        notes: [
          "Clean chip contacts monthly using an IPA cleaning card.",
          "Wipe mag-stripe slot with dry microfiber cloth.",
          "Avoid liquid cleaners or alcohol sprays directly on the device.",
          "Replace the device if the reader fails 3 times in a row — raise an RMA ticket.",
        ],
      },
    ],
  },
  transactions: {
    domainName: "Transactions",
    description: "Transaction history, failed transactions, reconciliation, and settlements.",
    entries: [
      {
        topic: "Transaction History",
        description: "View, search, and export transactions.",
        steps: [
          "On device: Menu > Transactions > list or date-filter view.",
          "On portal: Reports > Transactions — filter by date, method, status, terminal ID, amount range.",
          "Export as CSV/Excel/PDF.",
          "Each transaction has a unique Airpay Reference Number (ARN).",
        ],
      },
      {
        topic: "Failed Transactions",
        description: "Debited customer but no receipt? Here's what to do.",
        steps: [
          "Check transaction status on device or portal — may show 'Pending Confirmation'.",
          "Tap 'Reconcile' or wait 15 minutes for auto-reconciliation.",
          "If customer account was debited but transaction shows failed, funds are auto-reversed within 5-7 working days.",
          "Customer can also raise a complaint with their bank referencing the ARN.",
        ],
      },
      {
        topic: "Reconciliation",
        description: "Match transactions to settlements and bank credits.",
        steps: [
          "Download the Settlement Report from portal > Reports > Settlements.",
          "Match the settlement batch ID with the credit line in your bank statement.",
          "Any discrepancy (missing ARN, partial amount) — raise a ticket with batch ID + ARN.",
          "Use the Tally/Zoho connector for automated daily reconciliation.",
        ],
      },
      {
        topic: "Settlement Reports",
        description: "Track daily payouts from Airpay to your bank.",
        notes: [
          "Settlements batched per day, credited next working day by 11:00 AM (T+1).",
          "Cutoff: transactions after 8 PM move to next day's batch.",
          "Each settlement line item shows gross amount, MDR, GST, and net credit.",
          "UTR (bank reference) is posted once the credit is processed.",
        ],
      },
      {
        topic: "Void vs Refund",
        description: "Understand the difference.",
        notes: [
          "Void: same-day reversal of a transaction before settlement — funds never leave customer account.",
          "Refund: reversal after settlement — takes 5-7 working days, funds re-credited to card.",
          "Void is preferred when the customer is still at the counter.",
        ],
      },
    ],
  },
};
