#!/bin/sh
set -e

# Start MongoDB bound to localhost only
mongod --dbpath /data/db --bind_ip 127.0.0.1 --logpath /var/log/mongod.log &

# Wait up to 30 seconds for MongoDB to be ready
python3 - <<'EOF'
import sys, time
import pymongo

for _ in range(30):
    try:
        pymongo.MongoClient('mongodb://127.0.0.1:27017/', serverSelectionTimeoutMS=1000).admin.command('ping')
        print("MongoDB is ready.")
        sys.exit(0)
    except Exception:
        time.sleep(1)

print("ERROR: MongoDB did not start in time.", file=sys.stderr)
sys.exit(1)
EOF

# Write database config (writes ~/.config/moirai/config.json then exits)
moirai --db=mongodb --host=127.0.0.1

# Seed default admin password (single-user system; username is "admin" by convention)
moirai --set-password=admin

exec moirai "$@"
