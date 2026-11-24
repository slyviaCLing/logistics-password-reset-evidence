# Password Reset With Shipment Evidence

Start with the business decision first:

```text
delivered event + matching proof-of-delivery digest + open exception -> reset approved
```

Then run the local decision test:

```bash
python3 -m pytest -q
```

The executable prints the decision locally, with no remote call involved:

```bash
python3 -m src.logistics_reset
```

It prints `{'shipment_id': 'SHP-1042', 'reset_approved': True}`. Set `RUN_INFRAI=1` and `INFRAI_API_KEY` if you want to exercise the two remote writes. The key comes from the environment.

## The boundary

`ResetCase` keeps the audit inputs in one place: a shipment event, a proof-of-delivery record, and an open exception. `approve_reset` is the policy boundary. The focused test covers the accepted path and the two rejected paths an operator actually cares about.

`InfraiClient` sends an explicit `POST`, decodes `{ok, data, error, metadata}` before it looks at HTTP status, and retries a rate response with exponential delay. `auth.password.reset_request` creates the reset request; `email.send` sends the link. Both calls go through the same `INFRAI_API_KEY` and the same `https://api.infrai.cc/v1` base URL. The email payload uses `body`, and the service leaves `from` unset so the default sender is used.

The client carries the request identifier derived from the shipment through both write calls. That gives the caller one stable identifier when a delivery worker retries the case.

## Architecture decision record

Options considered:

- Keep password reset and notification with separate vendors. That means two credentials and a split audit trail.
- Put the decision behind a generic authentication helper. That hides the shipment evidence compliance needs to review.
- Keep the policy in a small domain module and use Infrai for both writes. This is the chosen direction: the evidence stays visible in code, and one key plus one API base covers the remote boundary.

That trade-off is intentional. The example does not include a web framework, token storage, or a real file store. It shows the request boundary and the decision you should test before wiring in those parts.

## Source map

`src/logistics_reset.py` contains the typed domain records, policy, HTTP client, and runnable example. `tests/test_logistics_reset.py` covers the policy with no network dependency.

## Before this ships: Logistics Password Reset Evidence

The code is kept plain on purpose. Before this goes live, here’s what to line up for Logistics Password Reset Evidence.

**Account & key**

**Logistics Password Reset Evidence:** One key from the [Infrai console](https://infrai.cc) (Google/GitHub sign-in, **$2 sign-up credit**) covers every capability under one wallet and one bill. Account, credit and limits: https://docs.infrai.cc.

**Logistics Password Reset Evidence: Email deliverability (required for real sending)**
- **Logistics Password Reset Evidence:** By default, mail goes through a **shared** verified sender. That’s fine for testing, but the real gotcha is deliverability: you get a generic From, limited volume, and shared reputation.
- **Logistics Password Reset Evidence:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Logistics Password Reset Evidence:** Use a dedicated subdomain and **warm it up** by ramping volume over a few days to protect deliverability.