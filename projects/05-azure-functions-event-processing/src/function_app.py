"""Azure Functions (Python v2 programming model) entry points."""
import json
import logging
import os

import azure.functions as func

from processor import (Ledger, PermanentError, TableIdempotencyStore, log_event, process)

app = func.FunctionApp()

_store = None
_ledger = Ledger()  # replace with the real downstream client


def store():
    global _store
    if _store is None:
        _store = TableIdempotencyStore(os.environ["AzureWebJobsStorage"])
    return _store


@app.queue_trigger(arg_name="msg", queue_name="orders", connection="AzureWebJobsStorage")
@app.queue_output(arg_name="poison", queue_name="orders-poison", connection="AzureWebJobsStorage")
def process_order(msg: func.QueueMessage, poison: func.Out[str]) -> None:
    try:
        process(msg.get_body().decode(), store(), _ledger,
                message_id=msg.id, dequeue_count=msg.dequeue_count)
    except PermanentError as exc:
        # Do not burn retries on a message that can never succeed.
        poison.set(json.dumps({"reason": str(exc), "body": msg.get_body().decode(),
                               "messageId": msg.id}))
        log_event(logging.ERROR, "permanent failure, sent to poison", outcome="poison",
                  messageId=msg.id, error=str(exc))
    # TransientError propagates: the host retries until maxDequeueCount (host.json),
    # then moves the message to orders-poison automatically.


@app.queue_trigger(arg_name="msg", queue_name="orders-poison", connection="AzureWebJobsStorage")
def poison_handler(msg: func.QueueMessage) -> None:
    log_event(logging.ERROR, "poison message received for review", outcome="poison-review",
              messageId=msg.id, body=msg.get_body().decode()[:500])
