import logging
import os
from inspect import Parameter, signature
from typing import Any, Callable, Dict, List, Tuple

from paho.mqtt.client import Client, MQTTMessage
from pydantic import BaseModel

from mate.tasks.pipeline import run_end_to_end
from mate_common.models.integration import Decl, Target

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)


class Bridge(Client):
    def __init__(self, broker_host: str, broker_port: int, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.handlers: Dict[str, Callable] = {}

    def on_connect(self, *_args: Any) -> None:
        logger.info(f"Connected to {self.broker_host}:{self.broker_port}.")
        for topic in self.handlers:
            logger.info("Activating handler for topic %s.", topic)
            self.subscribe(topic)
            self.message_callback_add(topic, self.handlers[topic])

    def send(self, topic: str, message: str) -> None:
        """Send a single message on a given topic."""

        logger.info("Sending message %s on topic %s.", message, topic)
        message_info = self.publish(topic, message)
        message_info.wait_for_publish()

    def listen(self) -> None:
        """Start listening for messages from the configured broker."""

        logger.info("Listening to messages from broker...")
        self.loop_forever()

    def handle(self, *topics: str):  # type: ignore
        """A decorator for registering type-aware message handlers.

        - This decorator takes as arguments any number of topics (topic wildcards) which the
          decorated handler should subscribe to.
        - The decorated handler function should take exactly two arguments:
            - The specific topic on which a given message came in on.
            - The message itself.
                - If no type annotation is provided for this argument, the raw message is passed in.
                - If a type annotation is provided for this argument, and that type is a pydantic model,
                  the message will be validated against that type, and the parsed model will be passed
                  into the handler. If validation fails, the message is dropped.
        """

        def register_handler(handler):  # type: ignore
            parameters: List[Tuple[str, Parameter]] = list(signature(handler).parameters.items())

            if len(parameters) != 2:
                logger.error("Message handler %s has invalid argument count.", handler.__name__)
                return handler

            message_type = parameters[1][1].annotation

            def is_pydantic_model(message_type: Any) -> bool:
                # See !1237 for why this is necessary
                try:
                    if issubclass(message_type, BaseModel):
                        return True
                    if hasattr(message_type, "__pydantic_model__") and issubclass(
                        message_type.__pydantic_model__, BaseModel
                    ):
                        return True
                except:
                    pass
                return False

            if is_pydantic_model(message_type):
                validate_message = True
            else:
                logger.warn(
                    "Message type %s for handler %s is not recognized; ignoring...",
                    message_type,
                    handler.__name__,
                )
                validate_message = False

            def topic_handler(_client: Client, _userdata: Any, message: MQTTMessage) -> None:
                if validate_message:
                    try:
                        parsed_message = message_type.__pydantic_model__.parse_raw(message.payload)
                    except:
                        logger.exception(
                            "Unable to parse message %s on topic %s into type %s; dropping.",
                            message.payload,
                            message.topic,
                            message_type,
                        )
                        return
                else:
                    parsed_message = message.payload

                handler(message.topic, parsed_message)

            for topic in topics:
                logger.info(
                    "Registering handler %s for messages of type %s on topic %s.",
                    handler.__name__,
                    message_type,
                    topic,
                )
                self.handlers[topic] = topic_handler
                logger.info("Activating handler for topic %s.", topic)
                self.subscribe(topic)
                self.message_callback_add(topic, topic_handler)

            return handler

        return register_handler


client = Bridge(broker_host="common_mosquitto", broker_port=1883)

# EXAMPLE:
@client.handle("decls")
def handle_decls(_topic: str, message: Decl) -> None:
    logger.info("Handled Decl message %s", repr(message))


@client.handle("public/challenge-broker/target/#")
def handle_challenge_broker_target(_topic: str, target: Target) -> None:
    base_url = os.getenv("MATE_SERVER_BASE", "http://server:8000/api/v1/")
    logger.info("Handled CB target message %s", repr(target))
    run_end_to_end.delay(base_url, target.id)


@client.handle("#")
def handle_all(_topic: str, message) -> None:  # type: ignore # intentionally untyped
    logger.info("Handled message %s on topic %s", repr(message), _topic)


def initialize() -> None:
    """Initialize the MQTT client.

    Necessary for both sending and receiving messages.
    """

    logger.info("Connecting to broker...")
    client.connect(client.broker_host, client.broker_port)


if __name__ == "__main__":
    initialize()
    client.listen()
