# Mon-bot import threading
from http.server import SimpleHTTPRequestHandler, HTTPServer

def run_fake_server():
    server = HTTPServer(('0.0.0.0', 10000), SimpleHTTPRequestHandler)
    server.serve_forever()

# Lance un faux serveur en arrière-plan pour tromper Render
threading.Thread(target=run_fake_server, daemon=True).start()

# Ton bot se lance enfin normalement
bot.run(os.getenv('DISCORD_TOKEN'))
