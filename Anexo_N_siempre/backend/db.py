import os

_db = None


def get_db():
    global _db
    if _db is None:
        from supabase import create_client

        _db = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
    return _db
