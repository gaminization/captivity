#!/usr/bin/env python3
"""
Fake Captive Portal Server for Chaos Testing.

Simulates:
- Redirects (302)
- Intercepted 200 OKs with CAPTCHAs
- Intercepted 200 OKs with forms
- Delayed responses (tarpit)
- Spoofed 204s (with HTML body attached)
"""

import http.server
import socketserver
import time
import random
import logging

PORT = 8080

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class ChaosPortalHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # 10% chance of tarpit delay
        if random.random() < 0.10:
            delay = random.uniform(2.0, 6.0)
            logging.info(f"Chaos: Tarpitting connection for {delay:.1f}s")
            time.sleep(delay)

        # Decide behavior based on random choice
        choice = random.choice(["redirect", "captcha", "spoofed_204", "normal_form"])
        
        if choice == "redirect":
            logging.info(f"Chaos: Emitting 302 Redirect to {self.path}")
            self.send_response(302)
            self.send_header('Location', 'http://chaos-portal.local/login')
            self.end_headers()
        
        elif choice == "captcha":
            logging.info("Chaos: Emitting 200 OK with CAPTCHA")
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body>Please complete the g-recaptcha to access the internet.</body></html>")

        elif choice == "normal_form":
            logging.info("Chaos: Emitting 200 OK with Login Form")
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><form><input name='user'><input name='pass'></form></body></html>")
            
        elif choice == "spoofed_204":
            logging.info("Chaos: Emitting Spoofed 204 (with HTML body)")
            self.send_response(204)
            # A real 204 shouldn't have a body, but some portals do this
            # Our probe must detect this as PORTAL_DETECTED because of content-length/body
            body = b"<html><body>Hidden portal form</body></html>"
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), ChaosPortalHandler) as httpd:
        logging.info(f"Fake Captive Portal serving at port {PORT}")
        httpd.serve_forever()
