# Home Workout Generator — User Guide

## Running the web interface on a server

If you want the web interface always available -- not something you have
to remember to start by hand -- you can run it as its own standalone
process on a home server (a Raspberry Pi, an old laptop, anything that can
stay on), sitting behind [nginx](https://nginx.org/) and reached securely
from your other devices over [Tailscale](https://tailscale.com/) (a mesh
VPN) instead of exposing anything to the public internet.

**1. Get the code onto the server.** SSH into it, then clone the repo:
```
git clone <your repo's URL> home_workout_template_generator
cd home_workout_template_generator
```
or copy the project folder over some other way (`scp`, a USB drive,
whatever's easiest) if you'd rather not set up git on the server.

**2. Install dependencies into a virtual environment:**
```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
(A virtual environment isn't required, but keeps this off your system
Python -- worth doing on a Pi you'll also use for other things.)

**3. Get your data onto the server**, if you're moving from an existing
setup rather than starting fresh -- copy `data/history.json` (and
`data/web_config.json`, if you want to keep the same passcode) into the
project folder. Both are plain JSON and safe to copy by hand; nothing else
under `data/` needs to move (`data/backups/` will rebuild itself over
time).

**4. Set a web passcode directly on the server.** `data/web_config.json`
is per-install -- it won't already exist if you're setting up fresh, and
copying it over in step 3 already handles the "keep my existing passcode"
case. Either way, this is how you set (or change) it:
```
python web_main.py --set-passcode
```

**5. Run it once by hand to confirm it works:**
```
python web_main.py
```
This starts the web interface with no display needed, fine on a headless
server. By default it only listens on `127.0.0.1` -- not reachable from
anywhere on the network yet, on purpose (see `--host`'s own `--help` text
for why). Leave it running and continue to the next step from another
terminal (or `Ctrl+C` it once you've confirmed it starts without errors).

**6. Put nginx in front of it.** The Werkzeug server `web_main.py` starts
is fine for a single person on a home network, but it isn't meant to be
exposed directly -- nginx in front of it is the standard fix, and gives
you one consistent local port to point Tailscale at (and a natural pattern
to repeat if you self-host other tools alongside this one, each on its own
port):
```
sudo apt install nginx   # or however your distro installs it
sudo cp deploy/nginx-home-workout.conf /etc/nginx/sites-available/home-workout
sudo ln -s /etc/nginx/sites-available/home-workout /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```
This proxies `127.0.0.1:8050` (nginx) -> `127.0.0.1:5050` (the app) --
both still local-only at this point. Edit
`/etc/nginx/sites-available/home-workout` first if either port is already
taken by something else on this machine.

**7. Install [Tailscale](https://tailscale.com/download) on the server**
and sign in, joining the same tailnet as your other devices (your phone,
laptop, etc. -- install and sign into Tailscale on those too, if you
haven't already).

**8. Make the app reachable on your tailnet**, with a real HTTPS
certificate and zero public exposure, by pointing Tailscale at nginx's
port rather than the app's. `tailscale serve` takes the *external* HTTPS
port with `--https` and the *local* port to forward to as the plain
argument -- these don't have to match, and each external port can only
point at one thing, so if you're already running another self-hosted tool
this way (e.g. a budget tracker on `:8443`), pick a different external
port here, like `8444`:
```
sudo tailscale serve --bg --https=8444 8050
```
(**Not** `tailscale funnel`, which would expose it to the public internet
-- you don't want that here.) From any device on your tailnet, you can now
open `https://<your-server-name>.<your-tailnet>.ts.net:8444/` and reach it
from anywhere -- no port forwarding on your router, nothing reachable
outside your tailnet. Run `sudo tailscale serve status` any time to see
every port you've mapped this way, across all your self-hosted tools, in
one place. This also means [installing it to your phone's home
screen](../README.md) now gets a real HTTPS URL, which is what lets
Android's automatic install prompt show up (see the README's PWA section)
-- just use the `:8444` URL, not the bare hostname, when installing.

**9. Make it survive reboots**, by installing it as a systemd service
instead of running it by hand:
```
sudo cp deploy/home-workout-web.service /etc/systemd/system/
sudo nano /etc/systemd/system/home-workout-web.service   # edit User= and WorkingDirectory= to match your setup
sudo systemctl daemon-reload
sudo systemctl enable --now home-workout-web
```
Check it came up with `sudo systemctl status home-workout-web`, and
`journalctl -u home-workout-web -f` to watch its logs live. Since `tailscale
serve --bg` and nginx's `sites-enabled` symlink both persist across
reboots on their own (as long as Tailscale and nginx themselves start on
boot, which their own installers already set up), you don't need to redo
steps 6-8 after a reboot -- only the app's own systemd service needed that
explicit `enable`.

**Keep the app's own passcode login even with Tailscale.** Tailscale's
network-level access control is strong, but anyone who can reach any
device already on your tailnet (or whose Tailscale account is
compromised) could otherwise reach the app -- the passcode is a second,
independent layer worth keeping.
