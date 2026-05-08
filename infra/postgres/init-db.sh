#!/bin/bash
set -e

# This script runs ONCE when Postgres container is first created.
# It creates the 3 databases needed by our microservices.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE fintech_auth;
    CREATE DATABASE fintech_users;
    CREATE DATABASE fintech_transactions;

    GRANT ALL PRIVILEGES ON DATABASE fintech_auth TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE fintech_users TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON DATABASE fintech_transactions TO $POSTGRES_USER;
EOSQL

echo "Successfully created 3 fintech databases."
