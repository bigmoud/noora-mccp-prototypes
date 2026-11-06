# Live WhatsApp demo

You text from your **personal WhatsApp** (playing the family) to Meta's free **test number**
(playing Noora). Your message appears in the nurse inbox within a second, the profile writer
processes it, and you get the automatic acknowledgment on your phone. When the nurse presses
Send on the Copilot draft, that reply reaches your phone too.

```
your phone ──WhatsApp──▶ Meta test number ──▶ Meta webhook ──HTTPS──▶ tunnel ──▶ server on your laptop
     ▲                                                                              │
     └──────────── acknowledgment (automatic) + nurse reply (she presses Send) ◀────┘
```

Your personal number stays on your normal WhatsApp: it is only the *recipient*. Use synthetic
messages only. Never forward a real family's message.

## One-time setup (about 20 minutes)

### 1. Meta app and test number
1. Go to [developers.facebook.com/apps](https://developers.facebook.com/apps) → **Create App** →
   name it → **Connect with customers through WhatsApp** → pick or create a business portfolio
   → **Create app**.
2. **Start using the API** → *API Setup*. Meta gives you a free test number in the **From** box.
3. **To** box → *Manage phone number list* → add **your personal number** and enter the code
   WhatsApp sends you. (Test numbers only talk to verified numbers, up to 5.)
4. Click **Send message** to send the `hello_world` template to your phone. It arrives on your
   WhatsApp from the test number: save that contact. This is the number you'll text.

### 2. Copy four values into `profile-writer/.env`
`.env` is already prepared on your laptop with the API key, model and random tokens filled in.
Open it and fill these:

| `.env` line | Where to find it |
|---|---|
| `WHATSAPP_TOKEN` | *API Setup* → **Generate access token** (expires after about a day; see step 5) |
| `WHATSAPP_PHONE_NUMBER_ID` | *API Setup*, under the From number: **Phone number ID** (not the phone number) |
| `WHATSAPP_APP_SECRET` | *App settings → Basic* → **App secret** → Show |
| `ALLOWED_TEST_NUMBERS` | Your personal number, country code first, no `+` or spaces, e.g. `14155550123` |

### 3. Start the server and tunnel
```bash
brew install cloudflared            # once
cd ~/Documents/noora-mccp-prototypes/profile-writer
./scripts/start_live.sh
```
It prints a **Dashboard** link (open it: that's the nurse inbox) and a **Callback URL**
ending in `/webhook`.

### 4. Point Meta at it
*WhatsApp → Configuration → Webhook → Edit*:
- **Callback URL**: the one the script printed
- **Verify token**: the `WHATSAPP_VERIFY_TOKEN` value from `.env`
- **Verify and save**, then under *Webhook fields* → `messages` → **Subscribe**

### 5. Try it
Text the test number from your phone, e.g.
*"Namaste, main Sunita ka pati bol raha hoon, yeh mera phone hai. Uski delivery 3 November ko ho gayi."*

- Within a second or two: a new chat **Live tester ••••0123** in the inbox, and the
  acknowledgment on your phone.
- About 10 seconds later: the profile updates (Baby DOB, *pnc*, who holds the phone) and a
  Copilot draft appears. **Use reply → Send**, and it arrives on your phone.

## Demo day
- Make a **fresh access token** that morning (temporary ones expire), paste it in `.env`, run
  the script again, and **paste the new Callback URL into Meta** (it changes every restart).
- Text the test number once before presenting, to check the whole loop.
- For a token that doesn't expire: *Business Settings → System users → Add → Assign assets*
  (your app with full control, your WhatsApp account with full control) → **Generate token**
  with `whatsapp_business_messaging` and `whatsapp_business_management`.
- Backup: the hosted page with no server connected runs the offline demo.

## What's automatic and what isn't
- **Automatic:** the fixed acknowledgment (`AUTO_ACK_TEXT` in `.env`), at most once every 2 hours per
  chat, never after "STOP", only to allowlisted numbers. It is not written by AI and gives no advice
  beyond "call 108 in an emergency".
- **Never automatic:** anything medical. The Copilot draft waits for the nurse, as in Noora's service.
  Medical advice without a qualified person's review is also outside Anthropic's usage policy for
  health.

## Demo sticker (optional)
Add `DEMO_STICKER=true` to `.env` and restart. When someone asks for other families' data or the
system's internals, the suggested reply is the fixed line *"We can’t share anyone else’s
information; in an emergency call 108."* with a "let me stop you right there" sticker. **Use
reply** attaches it (× removes it), and **Send** delivers the sticker, then the text. Nothing is
sent without the nurse pressing Send. The sticker lives in `app/assets/`, not `web/`, so it is
never published on the public demo page. Demo only: never turn this on for real families.

## When something goes wrong

| What you see | Fix |
|---|---|
| Script says "Fill these in .env first" | Add the values it lists |
| "Verify and save" fails | The script isn't running, the URL is old, or the verify token doesn't match `.env` |
| Your text never shows up | Subscribed to `messages`? Your number in `ALLOWED_TEST_NUMBERS` exactly as WhatsApp sends it (country code, no `+`)? The server terminal shows `POST /webhook -> 200` when Meta delivers |
| `POST /webhook -> 401` in the terminal | Wrong `WHATSAPP_APP_SECRET` |
| No acknowledgment, error 190 in the audit | Access token expired: make a new one |
| Error 131030 | Your number isn't on the test number's recipient list (step 1.3) |
| Error 131047 when the nurse sends | More than 24 hours since your last text: text the number again |
| Anything else | Use the offline demo |

Meta's screens change often. If a menu name doesn't match, Meta's
[get-started guide](https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started)
has the current path.
