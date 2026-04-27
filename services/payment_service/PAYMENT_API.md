# Payment API — Frontend Integration Guide

## Overview

The payment flow is a 3-step process: **tokenize → initiate → poll**.

Card data never reaches TravelHub's backend in plain text. The tokenize endpoint receives sensitive data, validates it, and returns a short-lived token. All subsequent operations use the token only.

```
1. POST /payments/tokenize   →  { token }
2. POST /payments/initiate   →  { paymentId, status: "processing" }
3. GET  /payments/{id}       →  poll until status is "approved" or "declined"
```

---

## Step 1: Tokenize payment method

### `POST /api/v1/payments/tokenize`

The `method` field determines which fields are required. The endpoint validates the data and returns a token valid for 15 minutes.

### Credit/Debit Card

```json
POST /api/v1/payments/tokenize
{
  "method": "credit_card",
  "cardNumber": "4242424242424242",
  "cardHolder": "Carlos Martinez",
  "expiry": "12/28",
  "cvv": "123"
}
```

`method` accepts `"credit_card"` or `"debit_card"` — same fields for both.

**Validations:**
- Card number must pass Luhn check
- CVV must be 3-4 digits
- Expiry format: `MM/YY`, must not be in the past
- Card brand auto-detected: Visa (starts with 4), Mastercard (51-55), Amex (34/37)

### Digital Wallet

```json
POST /api/v1/payments/tokenize
{
  "method": "digital_wallet",
  "walletProvider": "paypal",
  "walletEmail": "carlos@email.com"
}
```

**Validations:**
- Provider and email are required
- Email must be a valid format

### Bank Transfer

```json
POST /api/v1/payments/tokenize
{
  "method": "transfer",
  "bankCode": "001",
  "accountNumber": "12345678901234",
  "accountHolder": "Carlos Martinez"
}
```

**Validations:**
- All three fields required
- Account number must be at least 6 digits

### Response (all methods)

```json
201 Created
{
  "token": "tok_a1b2c3d4e5f6...",
  "method": "credit_card",
  "displayLabel": "Visa •••• 4242",
  "expiresAt": "2026-04-17T04:30:00Z",
  "cardLast4": "4242",
  "cardBrand": "visa",
  "walletProvider": null,
  "bankCode": null
}
```

- `displayLabel` is a human-readable label for the selected method. Use this in the UI to show the payment summary.
- Card-specific fields (`cardLast4`, `cardBrand`) are null for non-card methods.
- `walletProvider` is null for non-wallet methods.
- `bankCode` is null for non-transfer methods.
- Token expires in 15 minutes (same as the cart hold).

### Errors

| Status | Cause |
|--------|-------|
| 400 | Invalid card number (Luhn), expired card, bad CVV, missing fields |
| 422 | Malformed request (missing required fields for the selected method) |

---

## Step 2: Initiate payment

### `POST /api/v1/payments/initiate`

**Requires `X-User-Id` header.**

```json
POST /api/v1/payments/initiate
X-User-Id: c1000000-0000-0000-0000-000000000001

{
  "token": "tok_a1b2c3d4e5f6...",
  "cartId": "d1000000-0000-0000-0000-000000000001",
  "method": "credit_card"
}
```

- `token`: from the tokenize step
- `cartId`: the cart's `id` field from `GET /api/v1/cart`
- `method`: must match the method used during tokenization

The payment service fetches the cart internally to get pricing and booking data. The client does not need to send amounts or booking details.

### Response

```json
202 Accepted
{
  "paymentId": "f1000000-0000-0000-0000-000000000001",
  "status": "processing",
  "amount": 892500.0,
  "currency": "COP",
  "method": "credit_card",
  "cardLast4": "4242",
  "cardBrand": "visa",
  "transactionId": null,
  "bookingId": null,
  "bookingCode": null,
  "message": null,
  "createdAt": "2026-04-17T04:15:00Z",
  "processedAt": null
}
```

**Important:** Status `202` means the payment is being processed asynchronously by the Payment Adapter (simulated gateway with 2-6 second delay). Do not navigate away — start polling immediately.

### Errors

| Status | Cause |
|--------|-------|
| 400 | Invalid or expired token |
| 401 | Missing or invalid `X-User-Id` header |
| 404 | Cart not found |
| 410 | Cart hold expired |

---

## Step 3: Poll for result

### `GET /api/v1/payments/{paymentId}`

Poll this endpoint every 1 second until `status` is no longer `"processing"`.

```json
GET /api/v1/payments/f1000000-0000-0000-0000-000000000001
```

### Approved

```json
200 OK
{
  "paymentId": "f1000000-...",
  "status": "approved",
  "amount": 892500.0,
  "currency": "COP",
  "method": "credit_card",
  "cardLast4": "4242",
  "cardBrand": "visa",
  "transactionId": "txn_abc123def456...",
  "bookingId": null,
  "bookingCode": null,
  "message": "Payment approved",
  "processedAt": "2026-04-17T04:15:02Z"
}
```

→ Navigate to success/confirmation screen.

**Note:** `bookingId` and `bookingCode` may be null even on approval — the booking is created asynchronously by a downstream consumer. The client should not depend on these fields being present in the poll response.

### Declined

```json
200 OK
{
  "paymentId": "f1000000-...",
  "status": "declined",
  "message": "Payment declined",
  ...
}
```

→ Show a generic error message. Do **not** display the internal `message` field to the user. Use a localized string like:
- ES: "No se pudo procesar la transaccion. Verifique los datos o contacte a su banco."
- EN: "The transaction could not be processed. Please check your details or contact your bank."

The user can retry — the token and cart hold are still active.

---

## Test cards

For testing in non-production environments, use these card numbers:

| Card Number | Result |
|-------------|--------|
| `4242 4242 4242 4242` | Approved |
| `4000 0000 0000 0002` | Declined (insufficient funds) |
| `4000 0000 0000 0069` | Declined (expired card) |
| Any other valid 16-digit | Approved |

Wallet and transfer methods always succeed in the simulated gateway.

---

## Frontend implementation checklist

### Payment method selection (separate ticket scope)

- [ ] Show 3 method options: Tarjeta, Billetera digital, Transferencia
- [ ] Only one method selectable at a time
- [ ] Selected method highlighted visually
- [ ] Show corresponding form based on selection:
  - Card: number, holder, expiry, CVV
  - Wallet: provider dropdown, email
  - Transfer: bank selector, account number, holder name
- [ ] "Continue" button disabled until method is selected and form is valid

### Payment processing (HU4.8 scope — already implemented)

- [ ] On "Pay" click: call tokenize → initiate → start polling
- [ ] Show processing spinner/overlay during polling
- [ ] On approved: navigate to confirmation
- [ ] On declined: show generic error, re-enable form for retry
- [ ] Card input masked (first 12 digits as dots, last 4 visible)
- [ ] Never send raw card data to `/initiate` — only the token

---

## Architecture note

```
Client → POST /initiate → 202 (processing)
         ↓
         Payment Adapter (async, 2-6s delay)
         ↓
         POST /{id}/confirmation (internal webhook)
         ↓
         Update status → Publish to SNS (CommandUpdate EventBus)
         ↓                    ↓
Client → GET /{id}      SNS fans out to:
         → approved       ├── payment-booking-queue → Booking Worker → creates pending booking
                          └── notification-queue    → (future) Notification Worker
```

- The **Payment Adapter** is a simulated external gateway that processes asynchronously and calls back the payment service via an internal webhook (`POST /payments/{id}/confirmation`).
- On approval, the payment service publishes a `payment_confirmed` event to the **SNS CommandUpdate topic** (central EventBus). SNS fans out to SQS queues:
  - `payment-booking-queue` → **Booking Worker** consumes the event and creates a pending booking
  - `notification-queue` → future notification consumer
- The payment service does **not** create bookings directly. This is why `bookingId`/`bookingCode` are null in the payment response.
