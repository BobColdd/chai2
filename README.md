# 🍃 Chai Yako — v1

Digital farm record-keeping for small- and large-scale tea farmers. Farmers self-register, add
their farm number(s), and log plucking kilos, pruning activity, tools, and notes — with a green
dashboard, live trend chart, tea news, and a rule-based farm assistant chatbot.

This is **version 1**: fully self-service, no factory involvement needed. A factory-owned version
(farmers registered by a real factory, tallyboys recording purchases live, receipts, notice board,
complaints) exists as a separate build and becomes **version 2** once a real factory is ready to
come on board and run it.

## Features

- Self-registration with one or more farm numbers per farmer
- Plucking log (kilos/day) with cumulative totals and a 30-day trend chart
- Pruning log (date, bushes pruned, type)
- Tool/equipment inventory with condition tracking
- Farm notes
- CSV export of plucking history
- Tea news page (live Kenyan tea market headlines, categorized, searchable)
- Kericho weather card
- Rule-based farm assistant chatbot, including a personalized "overview" of your own records
- Fully responsive, tea-green themed dashboard

## Local setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # edit SECRET_KEY if you like
python run.py
```

Visit `http://127.0.0.1:5000`. Uses local SQLite by default if `DATABASE_URL` isn't set.

## Deploying live on your own domain

This project deploys to Render the same way as before:

1. Push this project to a GitHub repo.
2. On Render: **New + → Blueprint**, point it at the repo. `render.yaml` provisions both the web
   service and a free Postgres database automatically.
3. Once it's deployed and working on the `*.onrender.com` URL Render gives you, connect your own
   domain:
   - In the Render dashboard, open your web service → **Settings → Custom Domains → Add Custom Domain**.
   - Enter your domain (e.g. `chaiyako.co.ke` or `app.chaiyako.co.ke`).
   - Render will show you a DNS record to add — usually a **CNAME** pointing your domain/subdomain
     at the value Render gives you (for a root/apex domain, Render instead gives you an **A record**
     IP, or recommends using a subdomain like `app.yourdomain.com` with a CNAME, since apex domains
     can't use CNAMEs under the DNS standard).
   - Add that record with whoever you registered the domain through (the DNS management page for
     your domain, not Render).
   - DNS changes can take anywhere from a few minutes to a few hours to propagate. Render will show
     the domain as "Verified" once it detects the record.
4. Render automatically issues a free SSL certificate for your custom domain once it's verified —
   no separate setup needed for HTTPS.

If you tell me which registrar you're using (e.g. Safaricom, Truehost, GoDaddy, Namecheap), I can
give you the exact click-by-click steps for adding that DNS record.

## What's intentionally NOT in v1

This is the self-service version. Anything requiring a real, operating factory — clerks recording
purchases, live buying-center status, official receipts, factory notices, complaints to a
manager — is a separate build (v2), because it only makes sense once an actual factory is ready to
register farmers and run buying centers through it. Nothing here blocks building that later; the
two can even coexist as separate deployments if needed.

## Project structure

```
app/
├── models.py       # Farmer (self-registration), Farm, PluckingRecord, PruningRecord, Tool, Note
├── auth.py         # register / login / logout
├── main.py         # dashboard + all record CRUD + CSV export
├── news.py         # tea news page (RSS)
├── chatbot.py      # rule-based farm assistant, incl. "overview" of your own records
├── static/css/style.css
└── templates/
config.py
run.py
requirements.txt
Procfile
render.yaml
```
