from dotenv import load_dotenv
from app.__bridge__ import create_app
#from app import create_app
import os
# ✅ Load environment variables from .env if available
load_dotenv()

app = create_app()

if __name__ == "__main__":
    # Check if we're in a production environment on Render
    if os.getenv('RENDER') is None:  # Not on Render, use SSL locally
        cert_path = os.path.join(os.getcwd(), 'certs', 'server.crt')
        key_path = os.path.join(os.getcwd(), 'certs', 'server.key')

        if os.path.exists(cert_path) and os.path.exists(key_path):
            print("SSL certificates found. Starting app with SSL.")
            app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=(cert_path, key_path))
        else:
            print("SSL certificates not found. Starting app without SSL.")
            app.run(debug=True, host='0.0.0.0', port=5000)
    else:  # On Render, don't use SSL manually
        print("Running on Render. Starting app without SSL.")
        app.run(debug=True, host='0.0.0.0', port=5000)
