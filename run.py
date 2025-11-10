from app import create_app
import logging, sys

# Send INFO+ to stdout so app.logger.info(...) is visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Ensure Flask’s logger is at INFO level



app = create_app()

app.logger.setLevel(logging.INFO)

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=8080)

