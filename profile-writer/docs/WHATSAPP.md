# Connecting WhatsApp (live demo)

The live demo sends messages from a real phone to a WhatsApp number that our server
listens to. Use **synthetic messages from your own phones only**. Never forward or retype
a real family's message.

If any of this fails on demo day, the hosted page's offline demo shows the same screens
from a recorded run, with no WhatsApp and no server (see `DEPLOY.md`).

## Which number should we use?

| | Meta's free test number (recommended) | Your own number |
|---|---|---|
| Cost | Free | Free to set up; Meta charges for some messages |
| Setup time | About 15 minutes | Longer: number verification, display-name review |
| Who can message it | Only phones you add and verify as recipients in the app (Meta's limit is 5) | Anyone |
| Business verification | Not needed | Not needed to start; needed to raise sending limits |
| What happens to the number | Nothing: it's Meta's | It can't stay on the normal WhatsApp app (see below) |
| Good for | This demo | A real pilot, run by Noora on Noora's accounts |

**Use the test number for the demo.** It only accepts messages from phones you've
verified, so a stranger can't send a real family's message into the prototype. Our server's
allowlist (`ALLOWED_TEST_NUMBERS`) is a second lock on top of that.

**About personal numbers.** A number used with the WhatsApp Cloud API can't stay registered
on the normal WhatsApp app at the same time. Using your personal number means removing it
from WhatsApp on your phone first, and you lose that account's chats. A spare SIM that has
never been on WhatsApp avoids that. Numbers on the *WhatsApp Business app* can sometimes keep
both through Meta's "coexistence" option, but that is usually set up through a solution
provider. Not worth it for a demo. Production would use a number Noora owns.

## Setup with the test number

You need a Facebook account. No company registration is needed.

1. **Create the app.** At [developers.facebook.com](https://developers.facebook.com) →
   *My Apps* → *Create app* → use case *Other* → type *Business*. Add the **WhatsApp**
   product. A test business account and a **test phone number** are created for you.
2. **Copy three values** from *WhatsApp → API Setup*:
   - *Temporary access token* → `WHATSAPP_TOKEN` (expires after 24 hours; make a new one
     on demo morning)
   - *Phone number ID* (not the phone number) → `WHATSAPP_PHONE_NUMBER_ID`
   - The test number itself, so you know where to send messages
3. **Add your phones as recipients.** Same page, *To* field → *Manage phone number list* →
   add each fellow's phone and enter the code WhatsApp sends.
4. **App secret.** *App settings → Basic → App secret → Show* → `WHATSAPP_APP_SECRET`.
   Every message Meta sends us is signed with it; unsigned ones are rejected.
5. **Make up a verify token.** Any random string → `WHATSAPP_VERIFY_TOKEN`.
6. **Allowlist your phones.** `ALLOWED_TEST_NUMBERS=919800000001,14155550123`: country
   code first, no `+`, commas between. Messages from any other number are dropped unread.
7. **Turn it on.** `WHATSAPP_LIVE=true`, then start the server (locally or on Render, see
   `DEPLOY.md`). It refuses to start in live mode if a value is missing.
8. **Point Meta at the server.** *WhatsApp → Configuration → Webhook → Edit*:
   - Callback URL: `https://<your-server>/webhook`
     (Render: `https://noora-profile-writer.onrender.com/webhook`; local: your ngrok or
     cloudflared `https://` address + `/webhook`)
   - Verify token: the string from step 5 → *Verify and save*. If it fails, the server is
     not reachable or the token doesn't match.
   - Under *Webhook fields*, **subscribe to `messages`**.
9. **Open the chat.** On *API Setup*, send the `hello_world` template to your phone. Reply
   from your phone with anything. That reply opens WhatsApp's 24-hour window and appears
   on the dashboard as "Live tester ••••0123".

## Checking it works without Meta

```bash
python3 -m scripts.send_test_webhook --from 919800000001 "Meri wife ki delivery 3 November ko hui"
```

This sends a correctly signed, Meta-shaped message to your local server. If it shows up on
the dashboard, the server side is fine and any problem is on Meta's side.

## Demo morning checklist

- [ ] Fresh temporary token in the server's environment; server restarted
- [ ] Render: open the dashboard 5 minutes early (the free plan sleeps and takes ~1 minute to wake)
- [ ] Send `hello_world`, reply "hi" from the demo phone: the 24-hour window is open
- [ ] Dashboard connected; "Live tester" visible

## When something goes wrong

| What you see | Likely cause | Fix |
|---|---|---|
| "Verify and save" fails | Server asleep or URL wrong; verify token differs | Open `https://<server>/healthz`; recheck the token |
| Phone message never appears | Not subscribed to `messages`; number not allowlisted; wrong app secret | Audit tab: `dropped_not_allowlisted` or `webhook_rejected_signature` tells you which |
| Nurse reply fails, error 131047 | 24-hour window closed | Reply from the phone first |
| Error 190 | Token expired | New temporary token, restart |
| Error 131030 | Recipient not on the test number's list | Add and verify the phone (step 3) |
| Anything else | | Switch to the offline demo tab and carry on |

Meta's interface changes often. If a menu name above doesn't match, the WhatsApp
*Getting started* guide in Meta's developer docs has the current path.
