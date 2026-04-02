# Arthashastra

A Discord bot that runs a gig economy game for a single server. Citizens take jobs, post and claim bounties, earn money, and get taxed by the government. Built to complement a governance-themed server.

---

## Features

- **Jobs & Progression**
  - Citizens can take any available job freely
  - Each job has its own XP-based level tree with promotions
  - Some promotions transition into entirely new jobs (e.g. Lawyer → Judge)
  - Quitting a job triggers a 48-hour re-employment cooldown

- **Bounty System**
  - Any member can post a bounty to the open market
  - Employees claim and negotiate the prize in a private bot-managed channel
  - Completion requires confirmation from both parties
  - Unconfirmed completions auto-resolve after 48 hours
  - XP awarded on completion, scaled to prize value

- **Economy**
  - Every citizen has a wallet
  - All payments are processed through the bot
  - Configurable tax rate deducted from every bounty payment
  - Tax collected goes to a bot-managed government treasury

- **Fines**
  - The Chief Justice can issue fines against citizens
  - Fines are deducted from wallets and logged as transactions

- **Leaderboard**
  - Top earners and highest XP holders tracked server-wide

---

## Tech Stack

- Python 3.12+
- discord.py
- SQLAlchemy
- MariaDB
- Alembic
- python-dotenv

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/neelophile/arthashastra.git
cd arthashastra
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file:
```env
TOKEN=your_discord_bot_token
GUILD=your_guild_id
URI=mysql+pymysql://user:password@localhost:3306/arthashastra
```

### 4. Start MariaDB and run migrations
```bash
mariadbd-safe &
alembic upgrade head
```

### 5. Run the bot
```bash
python bot.py
```

---

## Project Structure

```
arthashastra/
├── bot.py
├── config.json
├── .env
├── db/
│   ├── models.py
│   └── database.py
├── cogs/
│   ├── employment.py
│   └── jobs/
└── migrations/
```

---

## Roadmap

- [ ] Job-specific commands and unique mechanics per job
- [ ] Dispute resolution for contested bounties
- [ ] Treasury management commands for the Finance Minister
- [ ] Fine history and appeal system
- [ ] More jobs with unique progression trees

---

## Notes

- Designed for a single Discord server
- Not built for multi-server deployment

---

## Author

neelophile
