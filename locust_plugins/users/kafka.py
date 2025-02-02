import time
import functools
from locust import User
from locust_plugins import missing_extra

try:
    from confluent_kafka import Producer
except ModuleNotFoundError:
    missing_extra("confluent_kafka", "kafka")


class KafkaUser(User):
    abstract = True
    # overload these values in your subclass
    bootstrap_servers: str = None  # type: ignore
    configs: dict[str, str | int] = None

    def __init__(self, environment):
        super().__init__(environment)
        self.client: KafkaClient = KafkaClient(environment=environment, bootstrap_servers=self.bootstrap_servers,
                                               configs=self.configs)

    def on_stop(self):
        self.client.producer.flush(5)


def _on_delivery(environment, identifier, response_length, start_time, start_perf_counter, context, err, _msg):
    environment.events.request.fire(
        request_type="ENQUEUE",
        name=identifier,
        start_time=start_time,
        response_time=(time.perf_counter() - start_perf_counter) * 1000,
        response_length=response_length,
        context=context,
        exception=err,
    )


class KafkaClient:
    def __init__(self, *, environment, bootstrap_servers, configs=None):
        self.environment = environment
        self.producer = Producer({"bootstrap.servers": bootstrap_servers}, **configs)

    def send(self, topic: str, value: bytes, key=None, response_length_override=None, name=None, context={}):
        start_perf_counter = time.perf_counter()
        start_time = time.time()
        identifier = name if name else topic
        response_length = response_length_override if response_length_override else len(value)
        callback = functools.partial(
            _on_delivery, self.environment, identifier, response_length, start_time, start_perf_counter, context
        )
        self.producer.produce(topic, value, key, on_delivery=callback)
        response_length = response_length_override if response_length_override else len(value)

        self.producer.poll()
