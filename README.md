# DUPR Data Downloader

This DUPR data downloader pulls player and match history data for all players belonging
to a club. This program pulls data from all the players that our players have played against
even if they are not in the club, so the dataset can get pretty big.

The data is stored in a local sqlite3 database via SQLAlchemy (I am working on a Mac).
This is my yet another attempt to master SQLAlchemy ORM.

After normalizing the data, I am using datasette to analyze the data. It is a great tool.
Check it out!

## Setup Instructions

### 1. Install Dependencies

```bash
pip3 install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root with your DUPR credentials:

```bash
DUPR_USERNAME=your_email@example.com
DUPR_PASSWORD=your_password
DUPR_CLUB_ID=your_club_id
```

**Note:** You'll need to find your DUPR club ID. This can usually be found in the URL when viewing your club page on the DUPR website.

### 3. Run the Application

```bash
python3 duprly.py --help
```

### Available Commands

- `python3 duprly.py get-data` - Update all data from DUPR
- `python3 duprly.py get-player <player_id>` - Get a specific player
- `python3 duprly.py get-all-players` - Get all players from your club
- `python3 duprly.py get-matches <dupr_id>` - Get match history for a specific player
- `python3 duprly.py write-excel` - Generate Excel report
- `python3 duprly.py stats` - Show database statistics
- `python3 duprly.py update-ratings` - Update player ratings
- `python3 duprly.py build-match-detail` - Flatten match data for faster queries

### Getting Started

1. First, run `get-all-players` to download all players from your club
2. Then run `get-data` to download all match history and update ratings
3. Use `write-excel` to generate a spreadsheet report
4. Use `stats` to see how much data you have

## API Issues

Keeping a list of things I found. Note that this is NOT a public and supported API.
I am just documenting it as I try different calls.

- Player call returns no DuprId field.
- double (and singles?) rating is always returned in the ratings field, not the verified field even
  if the rating is verified according to the isDoublesVerified field
- Match history calls returns teams with players but only minimal fields, and the players have a different type of DuprId

## Design Issues

- because different player data gets returned between the match calls and the
  player calls, saving a player, which is a composite object, is messy
- don't yell at me for storing the user id and password in a plain text env file!
  Actually this is really bad practice - do not do it.

## ToDo

- fix the write_excel code -- which is still using the old tinyDB database interface
- write tests!

## SQLAlchemy notes

## Selecting directly into list of objects

- use session.scalar(select(Class).where().all()) instead of session.execute(...).scalars()
- returning objects cannot be use outside of the session scope afterwards!!?

## Joins and selecting columns

result = session.execute(
...     select(User.name, Address.email_address)
...     .join(User.addresses)
...     .order_by(User.id, Address.id)

## M-1 Foreign Key

- in the child, store a FK field, but also
- declare a relationship field that is for object level reference

'''
class Rating(Base):
    ...
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"))
    player: Mapped["Player"] = relationship(back_populates="rating")
'''
