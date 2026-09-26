\# Billing foundation (M37)



M37 introduces the \*local, provider-agnostic\* billing state and the

contract a real provider must satisfy in a later milestone.



\## Scope of M37



\- Local subscription state (source of truth for the app).

\- A `BillingProvider` Protocol.

\- A `FakeBillingProvider` for tests.

\- A billing event inbox with idempotency on

&#x20; `(provider, provider\_event\_id)`.

\- A subscription state machine.



\*\*Explicitly out of scope for M37:\*\*



\- Stripe / Paddle / PayPal / Braintree.

\- Real payment processing.

\- Real webhook receivers.

\- Invoices, taxes, coupons, proration.

\- Production billing credentials.



\## Subscription state machine



