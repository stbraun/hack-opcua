"""A OPC UA server implementing a simple mixer unit."""

from opcua import Server
from time import sleep

endpoint = "opc.tcp://127.0.0.1:4840"
data_spec = "server.xml"

def setup_server(endpoint: str) -> Server:
    server = Server()
    server.set_endpoint(endpoint)
    print("Starting server at " + endpoint)
    return server


if __name__ == "__main__":
    server = setup_server(endpoint)
    server.start()

