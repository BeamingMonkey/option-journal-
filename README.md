Sure! Here’s the full README.md content for you to copy all at once:

# Option Journal - Trading Journal Web App

A Flask web application to log and track your trading activity with user authentication and SQLite backend.

## Features

- User registration and login with secure password hashing
- Log trades with details like symbol, entry/exit price, quantity, currency, reason, and strategy
- Secure sessions with Flask-Login
- SQLite database backend
- Configuration via environment variables (`.env` support)

## Getting Started

1. Clone the repository:

   ```bash
   git clone https://github.com/BeamingMonkey/option-journal-.git
   cd option-journal-

2. (Optional) Create and activate a virtual environment:

python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate


3. Install dependencies:

pip install -r requirements.txt


4. Create a .env file in the project root and add:

FLASK_SECRET_KEY=your_secret_key_here


5. Run the app:

flask run


6. Open your browser at http://localhost:5000.



Notes

The app uses SQLite; the database file will be created automatically on first run.

Ensure your .env file is set up with a secret key.

Make sure your environment has all dependencies installed.


License

MIT License


