# Dhurandhar

A Discord bot that implements an economy, job system, and basic governance features (elections, parties, and clubs) for a single server.

---

## Features

- **Jobs & Progression**
  - Users can have jobs with levels and XP
  - Tracks job history and income

- **Economy**
  - Income tracking per user
  - Foundation for rewards and future extensions

- **Bounties**
  - Users can create and accept tasks with rewards
  - Includes basic negotiation logging

- **Elections**
  - Supports different election types (e.g. cabinet, club)
  - Candidates and voting system

- **Parties**
  - Create and manage political parties
  - Track membership

- **Clubs**
  - User-created groups with open or approval-based joining

---

## Tech Stack

- Python  
- discord.py  
- SQLAlchemy  
- python-dotenv  
- SQLite / PostgreSQL (via URI)

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/neelophile/dhurandhar.git  
cd dhurandhar
```

### 2. Install dependencies
pip install -r requirements.txt

### 3. Configure environment variables

Create a `.env` file:

TOKEN=your_discord_bot_token  
GUILD=your_guild_id  
URI=your_database_uri  

### 4. Initialize the database
```python  
>>> from db.database import init_db  
>>> init_db()
```

### 5. Run the bot
python bot.py

---

## Project Structure

dhurandhar/  
├── bot.py  
├── db/  
│   ├── models.py  
│   └── database.py  
└── .env  

---

## Notes

- Designed primarily for a single Discord server  
- Not optimized for large-scale or multi-server deployment  
- Some features may be incomplete  

---

## Author

neelophile
