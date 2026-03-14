# Captivity

![Status](https://img.shields.io/badge/status-v0.1--experimental-orange)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

An autonomous login client for WiFi captive portals.

Automatically logs into captive portal networks so you don't have to open a browser every time.

---

## Why This Exists

Many campus and public WiFi networks require users to repeatedly log into a captive portal.

Typical workflow:

1. connect to WiFi
2. open a browser
3. wait for the portal redirect
4. enter credentials

Captivity removes this manual step by automating the login process.

---

## Features

* Login to a Pronto Networks captive portal
* Uses `curl` for authentication requests
* Performs a connectivity check after login
* Simple command line script

---

## Quick Start

Clone the repository:

```bash
git clone https://github.com/gaminization/captivity
cd captivity
```

Edit the script and add your credentials:

```bash
USERNAME=""
PASSWORD=""
```

Run the script:

```bash
./login.sh
```

Captivity will trigger the captive portal, authenticate, and verify internet connectivity.

---

## License

This project is licensed under the Apache 2.0 License.
