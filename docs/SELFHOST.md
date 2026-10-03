# Running Quayline yourself

Issue 208. Everything here is one page, because a self-hoster decides in about a minute
whether to continue and a longer document loses them first.

## What this is

A container that audits one invoice at a time. You upload a PDF, it tells you what the
invoice got wrong under 46 CFR Part 541, and it produces a letter you can send. It
holds nothing between requests, so there is nothing to administer, back up, or lose.

## Start it

    docker compose up --build

Then open <http://127.0.0.1:8765/>.

That is the whole procedure. There is no database, no account, no configuration file
and no environment variable to set. The port is bound to loopback on the host, so it is
reachable from the machine and from nowhere else.

To stop it:

    docker compose down

## Check it is alive

    curl http://127.0.0.1:8765/healthz

`{"status": "ok"}`. The health check touches nothing but the process, so a failure
means the process is not running rather than that an invoice was odd.

## What it can and cannot do today

| | |
|---|---|
| Checks the 541.6 invoice disclosures | yes, 13 of the 20 clauses |
| Checks the free time arithmetic | yes |
| Recomputes the money | Maersk only, from transcribed tariff rates |
| Carrier rate coverage | 1 of 9 carriers |
| Stores your invoice | no, and it never writes one |
| Accounts, billing, tenancy | no |

The coverage line is the one to read. `quayline coverage` prints the same list at run
time, and the landing page states it on load. For the eight carriers without
transcribed rates you get the disclosure check and the day count, and the money is
reported as unresolved rather than estimated.

## Reaching it from another machine

The container binds to loopback on purpose. The intake refuses any other bind because
it holds a container number and a disputed amount and has no authentication, and that
is a property worth keeping.

To reach it from elsewhere, put a reverse proxy in front and let the proxy terminate
TLS. Do not add a flag to widen the bind; there is deliberately not one.

Caddy, which gets a certificate on its own:

    # Caddyfile
    quayline.example.com {
        reverse_proxy 127.0.0.1:8765
    }

nginx:

    server {
        listen 443 ssl http2;
        server_name quayline.example.com;

        location / {
            proxy_pass http://127.0.0.1:8765;
            proxy_set_header Host $host;
            # The intake caps uploads at 8 MiB. Keep nginx above that or it will
            # reject a large invoice with a 413 before the application can say
            # anything useful about it.
            client_max_body_size 10m;
        }
    }

If you put it on a network other than your own, add authentication at the proxy. The
application will not do it for you and will not pretend to.

## What it keeps

Nothing. The server holds the upload for the length of one request, audits it, renders
the response, and drops it. There is no volume to mount and no backup to take.

That is a decision rather than an omission. It removes a whole class of problem, and it
means you can run this on a machine you are about to wipe.

## Running it without the compose file

    docker build -t quayline .
    docker run --rm -p 127.0.0.1:8765:8765 quayline

## If the money does not resolve

If an audit says the rate rule does not resolve, check what it names before assuming
the carrier has no matching rule. `quayline coverage` lists the rules held and why a
block is not used, including blocks that are held but marked `UNVERIFIED` and therefore
deliberately not applied.

## Running without Docker

    python -m venv .venv && . .venv/bin/activate
    pip install -e '.[dev]'
    quayline serve

The container adds packaging, not dependencies. There are none at runtime.