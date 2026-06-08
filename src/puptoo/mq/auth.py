def kafka_auth_config(connection_info: dict) -> dict:
    """Build Kafka SASL/SSL auth config from Clowder connection info.

    Adopted from yuptoo's lib/config.py pattern. Single source of truth
    for auth config used by both consumer and producer.
    """
    config = {}
    broker = connection_info.get("brokers", [{}])[0]

    if broker.get("sasl"):
        sasl = broker["sasl"]
        config["security.protocol"] = "SASL_SSL"
        config["sasl.mechanisms"] = sasl.get("saslMechanism", "PLAIN")
        config["sasl.username"] = sasl.get("username", "")
        config["sasl.password"] = sasl.get("password", "")

    if broker.get("cacert"):
        config["ssl.ca.location"] = "/tmp/kafka-cacert"

    return config
