import json
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError
from app.core.config import settings

logger = logging.getLogger(__name__)

# create one producer instance shared across the whole app
# KafkaProducer is thread-safe so sharing is fine
producer = KafkaProducer(
    bootstrap_servers=settings.kafka_bootstrap_servers,

    # value_serializer converts your Python dict → JSON bytes
    # automatically before sending to Kafka
    # without this you'd have to manually call json.dumps() every time
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),

    # key_serializer converts the message key → bytes
    # keys are optional but useful for routing related messages
    # to the same partition (e.g. all AAPL orders together)
    key_serializer=lambda k: k.encode('utf-8') if k else None,

    # if Kafka is temporarily unavailable, retry up to 3 times
    # before giving up and raising an error
    retries=3,

    # wait up to 1 second for Kafka to acknowledge the message
    # before considering it failed
    request_timeout_ms=1000,
)


def publish(topic: str, data: dict, key: str = None):
    """
    publish an event to a Kafka topic

    topic  — which topic to write to e.g. 'trades.executed'
    data   — the event payload as a Python dict
    key    — optional routing key e.g. symbol name 'AAPL'
             messages with the same key always go to the same partition
             this guarantees ordering for related events

    returns True if published successfully, False if failed
    """
    try:
        future = producer.send(topic, value=data, key=key)

        # block until Kafka confirms receipt (up to 1 second)
        # in production you might make this async
        # but for now synchronous is simpler to reason about
        record_metadata = future.get(timeout=1)

        logger.info(
            f"published to {topic} "
            f"partition={record_metadata.partition} "
            f"offset={record_metadata.offset}"
        )
        return True

    except KafkaError as e:
        # log the error but don't crash the order placement
        # Kafka being down should not prevent orders from being placed
        # the trade still happened — we just couldn't publish the event
        logger.error(f"failed to publish to {topic}: {e}")
        return False