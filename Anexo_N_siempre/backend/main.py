from firebase_functions import https_fn, options

from app import app

SECRETOS = ["SUPABASE_SERVICE_ROLE_KEY"]


@https_fn.on_request(
    region="us-central1",
    memory=options.MemoryOption.MB_512,
    timeout_sec=60,
    max_instances=3,
    secrets=SECRETOS,
)
def api(req: https_fn.Request) -> https_fn.Response:
    with app.request_context(req.environ):
        return app.full_dispatch_request()
