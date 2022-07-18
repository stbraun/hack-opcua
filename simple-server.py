"""A simple OPC UA server loading a data model from an XML file."""

from opcua import Server
from time import sleep

endpoint = "opc.tcp://127.0.0.1:4840"
data_spec = "server.xml"

server = Server()
server.set_endpoint(endpoint)
print("Loading XML configuration from " + data_spec)
server.import_xml(data_spec)
print("Starting server at " + endpoint)
server.start()

