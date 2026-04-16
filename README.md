# Pear2Pear

Pear2Pear is a Flask-based social platform where users can share files via WebRTC (peer-to-peer), send messages, and manage connections/friendships.

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Code Architecture](#code-architecture)
- [Database Structure](#database-structure)
- [Installation & Usage](#installation--usage)

---

## Overview

The app has four main features:

1. **File Transfer** — peer-to-peer via WebRTC with optional AES-256 encryption
2. **Messaging** — real-time chat via Socket.IO
3. **Connections** — send, accept, and decline friend requests
4. **Profiles** — public or private profiles with avatar, age, and location

---

## Project Structure

```
pear2pear/
├── main.py              # Flask app, routes, Socket.IO events
├── models.py            # SQLAlchemy database models
├── seed.py              # Script to create test users
├── static/
│   ├── style.css        # All CSS for the entire app
│   ├── avatars/         # Uploaded profile pictures
│   └── bars-solid-full.svg
├── templates/
│   ├── base.html        # Base layout (header, nav, global Socket.IO)
│   ├── macros.html      # Reusable Jinja2 macro (avatar)
│   ├── index.html       # File transfer page
│   ├── conversation.html
│   ├── messages.html
│   ├── connecties.html
│   ├── profiles.html
│   ├── profile.html
│   ├── account.html
│   ├── login.html
│   ├── register.html
│   └── logout.html
└── instance/
    └── pear2pear.db     # SQLite database (created automatically)
```

---

## Code Architecture

### `main.py`

This is the central file of the app, split into four parts:

**1. `create_app()`**
The app factory. All Flask extensions are initialized here:
- `SQLAlchemy` for the database
- `CSRFProtect` for form security
- `SocketIO` for real-time communication
- `LoginManager` for session/authentication management

SQLite performance is also tuned here via PRAGMAs (WAL mode, cache, mmap).

**2. Forms (WTForms)**
Three form classes:
- `LoginForm` — username + password
- `RegisterForm` — includes validation for unique username/email
- `EditProfileForm` — profile management, including privacy toggles

**3. `register_routes(app)`**
All HTTP routes are registered here as nested functions. Overview:

| Route | Method | Description |
|---|---|---|
| `/` | GET | File transfer page (login required) |
| `/login` | GET/POST | Log in |
| `/register` | GET/POST | Register |
| `/logout` | GET | Log out |
| `/account` | GET/POST | Edit profile |
| `/account/avatar` | POST | Upload profile picture |
| `/connecties` | GET | All users + friends list |
| `/profile/<id>` | GET | A user's profile page |
| `/friend/add/<id>` | POST | Send a friend request |
| `/friend/accept/<id>` | POST | Accept a request |
| `/friend/decline/<id>` | POST | Decline a request |
| `/friend/remove/<id>` | POST | Remove a friend |
| `/messages` | GET | Conversation overview + notifications |
| `/messages/<id>` | GET/POST | Conversation with a specific user |
| `/messages/send/<id>` | POST | Send a message from a profile page |
| `/api/users/search` | GET | JSON search results for recipient selection |

There is also an `inject_nav_counts()` context processor that runs on every request and injects badge counters (pending requests, unread messages) into all templates.

**4. `register_socket_events(app)`**
Socket.IO events for real-time communication. There are two use cases:

*Messaging:*
- The server pushes `new_message` to the recipient via their personal room (`user_{id}`)
- The sender receives `new_message_sent` so other open tabs also update

*File transfer (WebRTC signaling):*
- `transfer_offer` — sends SDP offer + file metadata to the recipient
- `transfer_answer` — sends SDP answer back to the sender
- `transfer_decline` — signals a refusal
- `ice_candidate` — exchanges ICE candidates (both directions)
- `transfer_complete` — signals that the transfer is done

The server never stores any file data; it only acts as a signaling relay. The actual data flows directly peer-to-peer via WebRTC DataChannels.

---

### `models.py`

Four SQLAlchemy models. See also the [Database Structure](#database-structure) section below.

- **`User`** — user account with profile, privacy settings, and helper methods
- **`Friendship`** — friendship relation (pending/accepted) between two users
- **`Message`** — chat message from sender to receiver
- **`Notification`** — system notification (e.g. "X accepted your request")

Passwords are stored as a scrypt hash via Werkzeug. Compound database indexes are created for fast queries on friendship and message status.

---

### `static/style.css`

All styling lives in one file, organized into sections with comments:

- **Reset & base** — background color, fonts, links
- **Header / dropdown / nav badge** — the top navigation bar
- **Buttons, forms, toggles, flash messages** — reusable UI components
- **Auth** — login/register pages
- **Profiles grid & cards** — user overview
- **Profile detail** — individual profile page
- **Messages & conversation** — message list and chat window
- **Connections** — friends strip and friend cards
- **File transfer page** — dropzone, progress bar, modals
- **Global toast** — notification at the bottom of the screen (all pages)

The color palette is purple/violet: background `#250064`, cards `#490064`, accent `#7c3aed`, highlight `#bb86fc`.

---

### `templates/base.html`

The base template that all other templates extend. Contains:
- The fixed header with dropdown navigation and badge counters
- The global toast notification (for messages and incoming files on every page)
- The global modals for incoming file transfers
- Socket.IO initialization and all global JavaScript for real-time events

---

### `seed.py`

Helper script to populate the database with test users:

```bash
python seed.py          # creates 20 users
python seed.py 50       # creates 50 users
python seed.py --clear  # removes all seed users
```

Password for all seed users: `wachtwoord`

---

## Database Structure

The SQLite database (`instance/pear2pear.db`) contains four tables:

### Table: `users`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Unique user ID |
| `username` | VARCHAR(30) | Unique username |
| `email` | VARCHAR(120) | Unique email address |
| `password_hash` | VARCHAR(256) | scrypt password hash |
| `created_at` | DATETIME | Registration date |
| `last_login` | DATETIME | Last login time |
| `age` | INTEGER | Optional age |
| `avatar` | VARCHAR(200) | Profile picture filename (stored in `static/avatars/`) |
| `location` | VARCHAR(100) | Optional location |
| `is_public` | BOOLEAN | Profile publicly visible |
| `friends_public` | BOOLEAN | Friends list publicly visible |

---

### Table: `friendships`

Stores both pending friend requests and accepted friendships.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | |
| `from_id` | INTEGER FK → users | Who sent the request |
| `to_id` | INTEGER FK → users | Who received the request |
| `status` | VARCHAR(10) | `"pending"` or `"accepted"` |
| `created_at` | DATETIME | |

A UNIQUE constraint on `(from_id, to_id)` prevents duplicate requests. The direction of `from_id`/`to_id` determines who initiated the request — this is needed to distinguish between `pending_sent` and `pending_received`.

---

### Table: `messages`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | |
| `sender_id` | INTEGER FK → users | Sender |
| `receiver_id` | INTEGER FK → users | Receiver |
| `body` | TEXT | Message text |
| `read` | BOOLEAN | Whether the message has been read |
| `created_at` | DATETIME | Sent date |

A compound index on `(sender_id, receiver_id)` makes fetching a conversation fast. A separate index on `(receiver_id, read)` makes counting unread messages fast.

---

### Table: `notifications`

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | |
| `user_id` | INTEGER FK → users | Who the notification is for |
| `body` | VARCHAR(300) | Notification text |
| `link` | VARCHAR(200) | Optional link (e.g. to a profile) |
| `read` | BOOLEAN | Whether the notification has been read |
| `created_at` | DATETIME | |

---

### Database Relationships (summary)

```
users ──< friendships   (from_id / to_id)
users ──< messages      (sender_id / receiver_id)
users ──< notifications (user_id)
```

---

## Installation & Usage

```bash
# 1. Install dependencies
pip install flask flask-sqlalchemy flask-login flask-socketio flask-wtf eventlet python-dotenv

# 2. Create a .env file
echo "SECRET_KEY=change-this-to-something-secret" >> .env
echo "DATABASE_URL=sqlite:///pear2pear.db" >> .env

# 3. Run the app
python main.py

# 4. (optional) Populate the database with test users
python seed.py 20
```

The app runs at `http://localhost:5000`.
