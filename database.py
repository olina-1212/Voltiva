
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables from .env
load_dotenv()

# Read the database URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is missing from .env")

# Use the psycopg PostgreSQL driver
DATABASE_URL = DATABASE_URL.replace(
    "postgresql://",
    "postgresql+psycopg://",
    1
)

# Create the database engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)


def test_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT 1")
            )

            print("Database connected successfully!")
            print("Test query result:", result.scalar())

    except Exception as error:
        print("Database connection failed!")
        print(type(error).__name__)


if __name__ == "__main__":
    test_connection()
