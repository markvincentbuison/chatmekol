from dotenv import load_dotenv
from app.__bridge__ import create_app

# Create the app
app = create_app()

if __name__ == "__main__":
    # Run the app in debug mode on all available interfaces (0.0.0.0) and with SSL
    app.run(debug=True, host="0.0.0.0", port=5000, ssl_context=('certs/server.crt', 'certs/server.key'))
