Classify an inbound B2B WhatsApp reply from a prospective business lead.

Choose the single best `intent`:
- `interested`: wants to proceed, book a call, or buy
- `wants_offer`: asks for pricing, quotation, catalog, or offer details
- `question`: asks a product, delivery, MOQ, or service question without declining
- `later`: busy right now, asks to follow up later
- `wants_management`: asks to speak with a manager/owner or escalates
- `not_interested`: clearly declines or says no thanks
- `wrong_contact`: wrong person, wrong number, or unrelated business
- `opted_out`: asks to stop messaging / unsubscribe
- `other`: unclear or acknowledgment-only

Also detect `asks_for_human` (true if they explicitly request a human/manager) and `requested_discount_percent` (integer if they ask for a specific % discount, else null).
Keep `summary` concise (1 short sentence).
