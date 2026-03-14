#!/bin/bash

USERNAME="" #enter your username here
PASSWORD="" #enter your password here

PORTAL="http://phc.prontonetworks.com/cgi-bin/authlogin" #change the portal to whatever is relevant to you (please note: the project has been tested only on pronto networks as of this commit)
COOKIE="/tmp/pronto_cookie"

echo "Triggering captive portal..."

curl -s -c $COOKIE "$PORTAL" > /dev/null

echo "Logging in..."

curl -s -b $COOKIE -c $COOKIE \
  -d "userId=$USERNAME" \
  -d "password=$PASSWORD" \
  -d "serviceName=ProntoAuthentication" \
  -d "Submit22=Login" \
  "$PORTAL" > /dev/null

echo "Checking internet..."

if curl -s --max-time 5 https://google.com > /dev/null; then
    echo "WiFi login successful!"
else
    echo "Login may have failed."
fi