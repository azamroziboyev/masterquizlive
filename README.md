# Enhanced Telegram Bot

A Telegram bot with enhanced admin broadcasting capabilities and improved guide section with video content.

## MasterQuiz - Telegram Quiz Bot with Web Interface

MasterQuiz is a Telegram bot that allows users to create, manage, and take quizzes. It features a web interface for a better user experience when taking quizzes.

## Features

- Create and manage quizzes with multiple-choice questions
- Take quizzes directly in Telegram or through a web interface
- Track quiz results and performance
- Multi-language support (Uzbek, Russian, English)
- Responsive design that works on both mobile and desktop

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- A Telegram Bot Token from [@BotFather](https://t.me/botfather)
- (Optional) Render.com account for deployment

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/masterquiz.git
   cd masterquiz
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root and add your Telegram bot token:
   ```env
   BOT_TOKEN=your_telegram_bot_token_here
   SESSION_SECRET=your_session_secret_here
   ```

## Running Locally

1. Start the bot:
   ```bash
   python main.py
   ```

2. In a separate terminal, start the web interface:
   ```bash
   gunicorn app:app --workers 4 --threads 2 --bind 0.0.0.0:8080 --timeout 120
   ```

3. The web interface will be available at `http://localhost:8080`

## Deployment

### Render.com

1. Fork this repository to your GitHub account
2. Create a new Web Service on Render.com and connect your GitHub repository
3. Use the following settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --workers 4 --threads 2 --bind 0.0.0.0:$PORT --timeout 120`
   - **Environment Variables**:
     - `BOT_TOKEN`: Your Telegram bot token
     - `SESSION_SECRET`: A random secret key for session encryption
     - `PYTHON_VERSION`: 3.9 (or your preferred Python version)

4. Deploy the application

## Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `BOT_TOKEN` | Your Telegram bot token | Yes | - |
| `SESSION_SECRET` | Secret key for session encryption | Yes | - |
| `PORT` | Port to run the web server on | No | 8080 |
| `PYTHONUNBUFFERED` | Recommended for Python in containers | No | true |

## Project Structure

```
masterquiz/
├── app.py                 # Web application (Flask)
├── main.py               # Telegram bot
├── requirements.txt      # Python dependencies
├── Procfile             # Process file for deployment
├── .env.example         # Example environment variables
├── .gitignore           # Git ignore file
├── README.md            # This file
└── telegram_webapp/     # Web interface
    ├── static/          # Static files (JS, CSS, images)
    └── templates/       # HTML templates
```

## Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [aiogram](https://docs.aiogram.dev/en/latest/) - Modern and fully asynchronous framework for Telegram Bot API
- [Flask](https://flask.palletsprojects.com/) - A lightweight WSGI web application framework
- [Render](https://render.com) - Cloud platform for hosting applications
   - Text guide with detailed instructions
   - Video tutorial support (manual.mp4)

## Setup

1. Clone this repository
2. Install dependencies:
   ```
   pip install python-telegram-bot
   ```
3. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `ADMIN_IDS`: Comma-separated list of admin Telegram user IDs
   
4. Place your `manual.mp4` video in the root directory
   
5. Run the bot:
   ```
   python main.py
   ```

## Bot Commands

- `/start` - Start the bot
- `/help` - Show help information
- `/guide` - Show guide with video tutorial
- `/admin` - Access admin panel (admins only)
- `/broadcast` - Start broadcast process (admins only)

## Admin Features

1. **Broadcasting**:
   - Text messages
   - Photos with captions
   - Videos with captions
   - Polls with multiple options
   
2. **User Statistics**:
   - View total user count

## File Structure

- `main.py` - Main bot file
- `config.py` - Configuration settings
- `database.py` - Database functions
- `keyboards.py` - Keyboard layouts
- `filters.py` - Custom filters
- `utils.py` - Utility functions
- `handlers/` - Command and message handlers

## Requirements

- Python 3.7+
- python-telegram-bot (v20.0+)
