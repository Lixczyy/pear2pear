"""
Vul de database met nep-gebruikers.

Gebruik:
    python seed.py          # vult 20 gebruikers (standaard)
    python seed.py 50       # vult 50 gebruikers
    python seed.py 10 --clear   # verwijdert eerst alle nep-gebruikers, dan 10 nieuwe
"""

import sys
import os
import random
import string

# ── Configuratie ─────────────────────────────────────────────────────────────
DB_PATH = os.path.join("instance", "pear2pear.db")
DEFAULT_PASSWORD = "wachtwoord"   # wachtwoord voor alle seed-accounts

FIRST_NAMES = [
    "Emma","Liam","Olivia","Noah","Ava","Elijah","Sophia","Lucas","Isabella","Mason",
    "Mia","Ethan","Amelia","Aiden","Harper","Caden","Evelyn","Grayson","Abigail","Jackson",
    "Nora","Sebastian","Aria","Mateo","Ella","Jack","Scarlett","Owen","Grace","Theodore",
    "Chloe","Levi","Victoria","Daniel","Riley","Henry","Zoey","Alexander","Penelope","William",
    "Lily","James","Eleanor","Benjamin","Hannah","Logan","Lillian","Samuel","Addison","David",
    "Lars","Sven","Ingrid","Bjorn","Astrid","Finn","Sigrid","Erik","Freya","Leif",
    "Mei","Yuki","Hiro","Sakura","Kenji","Aiko","Ryu","Yuna","Sota","Hana",
    "Mohamed","Fatima","Ahmed","Layla","Omar","Yasmin","Ali","Nadia","Karim","Sara",
]

LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Martinez","Wilson",
    "Anderson","Taylor","Thomas","Hernandez","Moore","Martin","Jackson","Thompson","White","Lopez",
    "Lee","Gonzalez","Harris","Clark","Lewis","Robinson","Walker","Perez","Hall","Young",
    "de Vries","Jansen","Bakker","Visser","Smit","Meijer","de Boer","Mulder","Berg","van Dijk",
    "Müller","Schmidt","Schneider","Fischer","Weber","Meyer","Wagner","Becker","Schulz","Hoffmann",
    "Dubois","Martin","Bernard","Lefebvre","Moreau","Laurent","Simon","Michel","Leroy","Roux",
]

CITIES = [
    "Amsterdam","Rotterdam","Den Haag","Utrecht","Eindhoven","Groningen","Tilburg","Almere",
    "Breda","Nijmegen","Enschede","Haarlem","Arnhem","Zaanstad","Amersfoort","Apeldoorn",
    "Zwolle","Maastricht","Dordrecht","Leiden","Leeuwarden","Deventer","Alkmaar","Delft",
    "Heerlen","Venlo","Roosendaal","Sittard","Ede","Hilversum","Emmen","Zoetermeer",
    "London","Paris","Berlin","Madrid","Rome","Vienna","Brussels","Amsterdam","Prague","Warsaw",
    "New York","Los Angeles","Chicago","Houston","Phoenix","Philadelphia","San Antonio","San Diego",
    "Tokyo","Seoul","Beijing","Shanghai","Singapore","Bangkok","Jakarta","Mumbai","Delhi","Osaka",
]

# ─────────────────────────────────────────────────────────────────────────────

def random_username(first, last):
    suffix = random.randint(10, 999)
    styles = [
        f"{first.lower()}{last.lower()}{suffix}",
        f"{first.lower()}.{last.lower()}",
        f"{first.lower()}_{suffix}",
        f"{first[0].lower()}{last.lower()}{suffix}",
    ]
    return random.choice(styles)[:30]

def random_email(username):
    domains = ["gmail.com","outlook.com","yahoo.com","hotmail.com","proton.me","icloud.com"]
    return f"{username}@{random.choice(domains)}"

def main():
    args = sys.argv[1:]
    count = 20
    clear = False

    for a in args:
        if a == "--clear":
            clear = True
        else:
            try:
                count = int(a)
            except ValueError:
                print(f"Onbekend argument: {a}")
                sys.exit(1)

    # Import Flask app so we get the right DB + password hashing
    from main import app
    from models import User, db

    with app.app_context():
        if clear:
            deleted = User.query.filter(User.username.like("%[seed]%")).delete()
            # Simpler: delete by email domain marker we embed
            deleted = db.session.execute(
                db.text("DELETE FROM users WHERE email LIKE '%@seed.fake'")
            ).rowcount
            db.session.commit()
            print(f"🗑  {deleted} seed-gebruikers verwijderd.")

        created = 0
        attempts = 0
        while created < count and attempts < count * 10:
            attempts += 1
            first = random.choice(FIRST_NAMES)
            last  = random.choice(LAST_NAMES)
            uname = random_username(first, last)
            email = f"{uname}@seed.fake"

            if User.query.filter((User.username == uname) | (User.email == email)).first():
                continue

            u = User(
                username  = uname,
                email     = email,
                age       = random.randint(16, 65) if random.random() > 0.2 else None,
                location  = random.choice(CITIES)  if random.random() > 0.15 else None,
                is_public = random.random() > 0.2,
            )
            u.set_password(DEFAULT_PASSWORD)
            db.session.add(u)
            created += 1

        db.session.commit()
        print(f"✅  {created} nep-gebruikers aangemaakt (wachtwoord: '{DEFAULT_PASSWORD}').")
        print(f"    Gebruik --clear om ze later te verwijderen.")

if __name__ == "__main__":
    main()
