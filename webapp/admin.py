import argparse
from rich.prompt import Prompt
from rich import print
from werkzeug.security import generate_password_hash
import sqlite3

parser = argparse.ArgumentParser()
parser.add_argument('-db', "--database", help="SQLite3 database file", required=True)
args = parser.parse_args()

con = sqlite3.connect(args.database)
cur = con.cursor()

print("[green]OpenCV Gauge Reader Web Admin Tool[/green]")

users = cur.execute("SELECT user,role from users").fetchall()


if len(users) > 0:
    print("Current users:")
    for user in users:
        print("[green bold]{u}[/green bold], role is [red]{r}[/red]".format(u=user[0], r=user[1]))
else:
    print("[red]NO CURRENT USERS[/red]")
          

user = Prompt.ask('Enter username', default='admin')
password = Prompt.ask("Enter password (empty to delete account)", password=True)

if password != '':
    role = Prompt.ask("Enter role", choices=['admin','user','api'], default='admin')

    print("[red]Hashing...[/red]")
    hash = str(generate_password_hash(password))

    print("[red]Updating database...[/red]")
    cur.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)", (user, hash, role))
    con.commit()

else:
    print("[red]Deleting account: {}[/red]".format(user))
    cur.execute("DELETE FROM users WHERE user = ?", (user,))
    con.commit()
    
print("Done.")


